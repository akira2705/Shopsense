"""
Browser Agent — ShopSense's eyes on the web.

The AI controls a real browser, navigates to product sites,
takes a screenshot, and uses Groq Vision (llama-4-scout-17b-16e-instruct)
to read prices, ratings, and reviews — exactly like a human would.

Sites:
  - Amazon.in      → general products (electronics, shoes, skincare, gym, etc.)
  - Flipkart.com   → laptops, TVs, headphones, fashion, appliances
  - CarWale.com    → new cars / bikes research
  - OLX.in         → used / second-hand items (cars, bikes, phones, furniture)
"""

import base64
import json
import os
import re
from typing import Optional

from openai import AsyncOpenAI
from playwright.async_api import async_playwright
try:
    from playwright_stealth import stealth_async as _stealth
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False
    print("[browser_agent] playwright-stealth not installed — bot detection may trigger")

_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ── Search URL templates ────────────────────────────────────────────────────

_SEARCH_URLS = {
    "amazon":   "https://www.amazon.in/s?k={query}",
    "flipkart": "https://www.flipkart.com/search?q={query}",
    "carwale":  "https://www.carwale.com/search/?q={query}",
    "olx":      "https://www.olx.in/items/q-{query}",
}

# ── Vision extraction prompts (site-aware) ──────────────────────────────────

_BASE_EXTRACT_PROMPT = """You are looking at a {site_label} search results screenshot.

Extract EVERY visible product. For each return:
- title: exact product name as shown on page
- price: INR as plain number (e.g. 1299). Ranges → use lower number. Null if not visible.
- rating: stars out of 5 as decimal (e.g. 4.3), null if not shown
- review_count: integer count of ratings/reviews, null if not shown
- review_highlight: ONE short phrase (max 8 words) summarising what buyers say — look for review snippets, "most liked", "verified buyer" text visible on page. Null if none visible.
- description: visible specs, highlights, tagline — 1-2 sentences. Include RAM, GPU, storage, mileage, seating, fuel type if shown.
- tags: keywords from title + description + specs. Include technical terms: rtx, oled, 144hz, 7 seater, diesel, etc.

{site_hints}

Return ONLY a valid JSON array, no other text:
[
  {{
    "title": "...",
    "price": 1299,
    "rating": 4.3,
    "review_count": 1500,
    "review_highlight": "Great battery, fast charging",
    "description": "...",
    "tags": ["tag1", "tag2"]
  }}
]

Rules:
- Skip products with no visible price
- Include ALL visible products even if some fields are null
- Be thorough with tags — include every spec keyword you can see
"""

_SITE_HINTS = {
    "amazon": "Amazon-specific: look for star ratings, 'X ratings', 'Sponsored', Prime badge. Extract specs from bullet points. Tags should include brand, key specs, use case.",
    "flipkart": "Flipkart-specific: look for star ratings, 'X ratings & Y reviews', 'Assured' badge. Tags should include brand, RAM, storage, display specs.",
    "carwale": "CarWale-specific: extract fuel type (petrol/diesel/CNG/electric/hybrid), mileage (kmpl or km/kg), seating capacity (5-seater/7-seater), transmission (manual/automatic/CVT). Tags MUST include these.",
    "olx": "OLX-specific: extract year, km driven, ownership (1st owner/2nd owner), condition. Tags should include these details. Prices may be negotiable.",
}

def _extract_prompt_for_site(site: str) -> str:
    labels = {"amazon": "Amazon.in", "flipkart": "Flipkart", "carwale": "CarWale", "olx": "OLX.in"}
    return _BASE_EXTRACT_PROMPT.format(
        site_label=labels.get(site, site),
        site_hints=_SITE_HINTS.get(site, ""),
    )


# ── Site routing ─────────────────────────────────────────────────────────────
# IMPORTANT: order matters — used/second-hand check before vehicle check,
# so "used car" → OLX, not CarWale (CarWale = new cars/bikes research)

def _pick_site(intent: dict) -> str:
    combined = (
        (intent.get("category") or "") + " " +
        (intent.get("use_case") or "") + " " +
        " ".join(intent.get("constraints", []) or [])
    ).lower()

    # ── Used / second-hand first (highest priority) ──────────────────────────
    _used_kw = [
        "used", "second hand", "secondhand", "second-hand",
        "pre-owned", "preowned", "pre owned", "old ", "refurbished",
        "preloved", "pre-loved",
    ]
    if any(w in combined for w in _used_kw):
        return "olx"

    # ── Vehicles (new cars / bikes / scooters) ───────────────────────────────
    _vehicle_kw = [
        "car", "cars", "bike", "bikes", "motorcycle", "motorcycles",
        "scooter", "scooters", "suv", "sedan", "hatchback", "vehicle",
        "vehicles", "auto", "swift", "alto", "i20", "creta", "nexon",
        "fortuner", "innova", "hycross", "innova hycross", "baleno", "brezza", "sonet", "venue",
        "ertiga", "carens", "xuv700", "xuv", "mpv", "muv",
        "activa", "splendor", "pulsar", "unicorn", "classic 350",
        "royal enfield", "tvs", "bajaj", "hero honda",
        "new car", "new bike", "buy car", "buy bike",
    ]
    if any(w in combined for w in _vehicle_kw):
        return "carwale"

    # ── Flipkart — laptops, TVs, appliances, fashion ─────────────────────────
    _flipkart_kw = [
        "laptop", "laptops", "notebook", "gaming laptop",
        "graphics card", "rtx", "nvidia", "gtx", "gpu",
        "television", "tv", "smart tv", "led tv",
        "refrigerator", "fridge", "washing machine", "dishwasher",
        "air conditioner", "ac ", " ac", "cooler",
        "headphone", "earphone", "earbuds",
        "fashion", "clothes", "clothing", "shirt", "jeans", "kurta",
        "dress", "saree", "ethnic", "footwear", "sandal", "heels",
        "monitor", "printer", "camera dslr",
    ]
    if any(w in combined for w in _flipkart_kw):
        return "flipkart"

    # ── Default: Amazon ───────────────────────────────────────────────────────
    return "amazon"


def _build_query(intent: dict) -> str:
    """Build a specific search query — include category, use_case, constraints, and budget."""
    parts = []

    category = (intent.get("category") or "").strip()
    if category:
        parts.append(category)

    use_case = (intent.get("use_case") or "").strip()
    # Only add use_case if it's meaningfully different from category
    if use_case and use_case.lower() not in category.lower():
        parts.append(use_case)

    # Include short hard constraints that narrow the search (seating, fuel, body type)
    for c in (intent.get("constraints") or [])[:3]:
        c_stripped = c.strip()
        if c_stripped and len(c_stripped) < 25 and c_stripped.lower() not in " ".join(parts).lower():
            parts.append(c_stripped)

    # Append budget as a search hint — sites like Flipkart and Amazon filter by it
    budget_max = intent.get("budget_max")
    if budget_max:
        if budget_max >= 100000:
            lakhs = budget_max / 100000
            parts.append(f"under {lakhs:.0f} lakh")
        else:
            parts.append(f"under {int(budget_max)}")

    return " ".join(p for p in parts if p) or "products"


# ── Site-specific wait selectors (what to wait for before screenshotting) ──

_WAIT_SELECTORS = {
    "amazon":   "[data-component-type='s-search-result']",
    "flipkart": "._1AtVbE",
    "carwale":  ".gsc-search-result, .listing-card, [class*='car-card'], [class*='CarCard']",
    "olx":      "[data-aut-id='itemBox'], .EIR5N",
}

# ── Site-specific image selectors (DOM extraction — more reliable than vision for images) ──

_IMAGE_SELECTORS = {
    "amazon":   "[data-component-type='s-search-result'] img.s-image",
    "flipkart": "._1AtVbE img, .CXW8mj img, ._396cs4 img",
    "carwale":  "[class*='card'] img, [class*='Card'] img, [class*='listing'] img",
    "olx":      "[data-aut-id='itemBox'] img, .EIR5N img",
}

# ── Browser + screenshot ────────────────────────────────────────────────────

async def _browse_and_extract(url: str, site: str, on_status=None) -> list[dict]:
    """
    Launch a stealth browser, scroll through the page in 3 steps,
    extract products from each scroll position + image URLs from DOM,
    deduplicate, and return the combined list.

    on_status: optional async callable(text: str) — called with live status updates
    """
    async def _status_cb(text: str):
        if on_status:
            try:
                await on_status(text)
            except Exception:
                pass

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 900},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                extra_http_headers={
                    "Accept-Language": "en-IN,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                },
            )
            page = await context.new_page()

            if _STEALTH_AVAILABLE:
                await _stealth(page)

            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
                window.chrome = { runtime: {} };
            """)

            print(f"[browser_agent] navigating → {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)

            # Wait for product cards
            selector = _WAIT_SELECTORS.get(site, "")
            if selector:
                try:
                    await page.wait_for_selector(selector, timeout=8000)
                    print(f"[browser_agent] ✓ product cards detected ({site})")
                except Exception:
                    print(f"[browser_agent] selector timeout — proceeding anyway")
                    await page.wait_for_timeout(3000)
            else:
                await page.wait_for_timeout(3000)

            # ── Take 3 screenshots at different scroll depths ──────────────
            screenshots_b64 = []
            scroll_positions = [0, 900, 1800]

            for i, scroll_y in enumerate(scroll_positions):
                await _status_cb(f"Reading results — section {i + 1} of {len(scroll_positions)}…")
                await page.evaluate(f"window.scrollTo(0, {scroll_y})")
                await page.wait_for_timeout(600)
                shot = await page.screenshot(type="jpeg", quality=75, full_page=False)
                b64 = base64.b64encode(shot).decode()
                screenshots_b64.append(b64)
                print(f"[browser_agent] screenshot at scroll={scroll_y} ({len(b64)//1024}KB)")

            # ── Extract product image URLs directly from the DOM ───────────
            img_urls: list[str] = []
            try:
                img_sel = _IMAGE_SELECTORS.get(site, "")
                if img_sel:
                    # Escape single quotes for JS string
                    js_sel = img_sel.replace("'", "\\'")
                    img_urls = await page.evaluate(f"""
                        () => {{
                            const imgs = document.querySelectorAll('{js_sel}');
                            return Array.from(imgs)
                                .map(img =>
                                    img.src ||
                                    img.getAttribute('data-src') ||
                                    img.getAttribute('data-lazy-src') || ''
                                )
                                .filter(src =>
                                    src &&
                                    src.startsWith('http') &&
                                    !src.includes('data:image/gif') &&
                                    !src.includes('placeholder') &&
                                    src.length > 30
                                );
                        }}
                    """)
                    print(f"[browser_agent] {len(img_urls)} image URLs extracted from DOM")
            except Exception as img_err:
                print(f"[browser_agent] image URL extraction failed: {img_err}")

            await browser.close()

        # ── Extract products from each screenshot, deduplicate ─────────────
        await _status_cb("AI vision reading products…")
        all_products: list[dict] = []
        seen_titles: set[str] = set()

        for i, b64 in enumerate(screenshots_b64):
            extracted = await _vision_extract(b64, site)
            new_count = 0
            for p in extracted:
                title_key = p.get("title", "").lower().strip()[:60]
                if title_key and title_key not in seen_titles:
                    seen_titles.add(title_key)
                    all_products.append(p)
                    new_count += 1
            print(f"[browser_agent] scroll {i}: {new_count} new products (total {len(all_products)})")

        # ── Attach image URLs to products by position on page ─────────────
        for i, p in enumerate(all_products):
            if i < len(img_urls) and not p.get("image_url"):
                p["image_url"] = img_urls[i]

        print(f"[browser_agent] ✓ {len(all_products)} unique products extracted")
        return all_products

    except Exception as exc:
        print(f"[browser_agent] browse error: {exc}")
        return []


# ── Vision extraction ───────────────────────────────────────────────────────

async def _vision_extract(screenshot_b64: str, site: str) -> list[dict]:
    """Send screenshot to Groq Vision and parse product list."""
    try:
        response = await _client.chat.completions.create(
            model=_VISION_MODEL,
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{screenshot_b64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": _extract_prompt_for_site(site),
                        },
                    ],
                }
            ],
        )
        raw = response.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            print(f"[browser_agent] vision returned no JSON array")
            return []

        items = json.loads(match.group())
        products = []
        for i, item in enumerate(items):
            price = float(item.get("price") or 0)
            if price <= 0:
                continue
            products.append({
                "id": f"{site}_{i}",
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "tags": list(item.get("tags") or []) + [site],
                "price": price,
                "rating": item.get("rating"),
                "review_count": item.get("review_count"),
                "review_highlight": item.get("review_highlight"),
                "image_url": None,
                "variant_id": None,
                "source": site,
            })
        return products

    except Exception as exc:
        print(f"[browser_agent] vision extraction error: {exc}")
        return []


# ── Public API ──────────────────────────────────────────────────────────────

def _status(text: str) -> dict:
    return {"type": "status", "text": text}


def _sanity_filter(products: list[dict], intent: dict) -> list[dict]:
    """
    Remove products with clearly impossible prices for the category.
    Prevents vision misreads (e.g. EMI ₹12,499/mo read as full car price).
    Always returns at least one product — falls back to full list if everything is filtered.
    """
    category = (intent.get("category") or "").lower()

    def _min_price(p: dict) -> int:
        tags_text = " ".join(p.get("tags", [])).lower()
        title_text = p.get("title", "").lower()
        combined = category + " " + tags_text + " " + title_text

        if any(w in combined for w in ["car", "suv", "sedan", "hatchback", "mpv", "muv"]):
            return 50000
        if any(w in combined for w in ["bike", "motorcycle"]):
            return 5000
        if any(w in combined for w in ["laptop", "notebook"]):
            return 8000
        if any(w in combined for w in ["smartphone", "phone", "iphone"]):
            return 2000
        if any(w in combined for w in ["tv", "television", "refrigerator", "washing machine"]):
            return 3000
        return 50   # for accessories, skincare, etc.

    filtered = [p for p in products if p.get("price", 0) >= _min_price(p)]
    return filtered if filtered else products


async def search_products_stream(intent: dict, limit: int = 15):
    """
    Async generator — yields status dicts then a final products dict.
    Streams live status from inside the browser loop via asyncio Queue.
    """
    import asyncio

    site = _pick_site(intent)
    query = _build_query(intent)
    site_labels = {"amazon": "Amazon.in", "flipkart": "Flipkart", "carwale": "CarWale", "olx": "OLX.in"}
    label = site_labels.get(site, site)
    url = _SEARCH_URLS[site].format(query=query.replace(" ", "+"))

    yield _status(f"Opening {label}…")

    # ── Stream live status from browser via asyncio Queue ──────────────────
    q: asyncio.Queue = asyncio.Queue()

    async def on_status(text: str):
        await q.put(text)

    browser_task = asyncio.create_task(_browse_and_extract(url, site, on_status=on_status))

    # Drain queue while browser is working — yields status to frontend live
    while not browser_task.done():
        try:
            text = await asyncio.wait_for(q.get(), timeout=0.4)
            yield _status(text)
        except asyncio.TimeoutError:
            pass

    # Drain any remaining status messages
    while not q.empty():
        yield _status(q.get_nowait())

    products = await browser_task

    if products:
        yield _status(f"AI vision found {len(products)} products — filtering…")
        products = _sanity_filter(products, intent)

    budget_max = intent.get("budget_max")
    if budget_max:
        within = [p for p in products if p["price"] <= budget_max]
        if within:
            products = within  # only apply if it doesn't wipe everything

    count = len(products)
    yield _status(f"Found {count} product{'s' if count != 1 else ''} — ranking by confidence…")
    yield {"type": "products", "data": products[:limit]}


async def search_products_broad_stream(intent: dict):
    """Broad fallback — also yields status events."""
    site = _pick_site(intent)
    site_labels = {"amazon": "Amazon.in", "flipkart": "Flipkart", "carwale": "CarWale", "olx": "OLX.in"}

    # Fallback site logic
    fallback_map = {"amazon": "flipkart", "flipkart": "amazon", "carwale": "olx", "olx": "carwale"}
    fallback_site = fallback_map.get(site, "amazon")

    # Preserve the full intent so budget/constraints/use_case aren't lost
    loose_intent = {
        "category": intent.get("category", ""),
        "use_case": intent.get("use_case", ""),
        "budget_max": intent.get("budget_max"),
        "constraints": intent.get("constraints", []),
        "priorities": intent.get("priorities", []),
    }
    products = []

    async for event in search_products_stream(loose_intent, limit=10):
        if event["type"] == "products":
            products = event["data"]
        else:
            yield event

    if not products:
        import asyncio
        label = site_labels.get(fallback_site, fallback_site)
        yield _status(f"Trying {label} instead…")
        query = _build_query(loose_intent)
        url = _SEARCH_URLS[fallback_site].format(query=query.replace(" ", "+"))
        q2: asyncio.Queue = asyncio.Queue()
        async def _on_status2(t: str): await q2.put(t)
        task2 = asyncio.create_task(_browse_and_extract(url, fallback_site, on_status=_on_status2))
        while not task2.done():
            try:
                yield _status(await asyncio.wait_for(q2.get(), timeout=0.4))
            except asyncio.TimeoutError:
                pass
        while not q2.empty():
            yield _status(q2.get_nowait())
        products = await task2
        if products:
            products = _sanity_filter(products, intent)

    yield {"type": "products", "data": products}



async def create_cart(variant_id: str, quantity: int = 1) -> Optional[str]:
    """Not applicable for browser-sourced products."""
    return None
