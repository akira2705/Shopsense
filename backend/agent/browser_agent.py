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

import asyncio
import base64
import json
import os
import re
from typing import Optional
from urllib.parse import quote_plus

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

# ── Fallback direct-search URLs (used only if Google gives 0 links) ─────────

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
    labels = {
        "amazon": "Amazon.in", "flipkart": "Flipkart",
        "carwale": "CarWale / CarDekho / Cars24", "olx": "OLX.in",
        "generic": "product listing page",
    }
    return _BASE_EXTRACT_PROMPT.format(
        site_label=labels.get(site, site),
        site_hints=_SITE_HINTS.get(site, "Extract every visible product with title, price, and specs."),
    )


def _detect_site(url: str) -> str:
    """Map a URL to a site key for the right vision prompt."""
    u = url.lower()
    if "amazon.in" in u:   return "amazon"
    if "flipkart.com" in u: return "flipkart"
    if any(s in u for s in ["carwale.com", "cardekho.com", "cars24.com",
                              "zigwheels.com", "spinny.com", "droom.in"]): return "carwale"
    if "olx.in" in u:       return "olx"
    return "generic"


_INDIAN_CITIES = {
    "coimbatore", "chennai", "bangalore", "bengaluru", "mumbai", "delhi",
    "hyderabad", "pune", "kolkata", "ahmedabad", "jaipur", "surat",
    "lucknow", "kanpur", "nagpur", "indore", "thane", "bhopal",
    "visakhapatnam", "pimpri", "patna", "vadodara", "ghaziabad", "ludhiana",
    "agra", "nashik", "faridabad", "meerut", "rajkot", "varanasi", "kochi",
    "madurai", "salem", "trichy", "tiruchirappalli", "erode", "vellore",
}


def _build_google_query(intent: dict) -> str:
    """
    Build a targeted Google search query from intent.
    Brand always goes first. City name included if mentioned in constraints/use_case.
    E.g. "BMW car for sale Coimbatore under 1 crore india"
    """
    parts = []
    city = None

    # Extract brand from constraints
    brand = None
    other_constraints = []
    for c in (intent.get("constraints") or []):
        c = c.strip()
        if not c:
            continue
        if c.lower().startswith("brand:"):
            brand = c.split(":", 1)[1].strip()
        else:
            # Check if this constraint is a city name
            c_lower = c.lower()
            if any(city_kw in c_lower for city_kw in _INDIAN_CITIES):
                city = c  # keep as city
            elif len(c) < 30:
                other_constraints.append(c)

    # Also look for city in use_case or category
    for field in [intent.get("use_case") or "", intent.get("category") or ""]:
        if not city:
            for city_kw in _INDIAN_CITIES:
                if city_kw in field.lower():
                    city = city_kw.title()
                    break

    # Brand always first
    if brand:
        parts.append(brand)

    category = (intent.get("category") or "").strip()
    if category:
        # Don't repeat brand in category
        cat_clean = re.sub(re.escape(brand or ""), "", category, flags=re.IGNORECASE).strip() if brand else category
        if cat_clean:
            parts.append(cat_clean)

    # Add "for sale" for vehicle/used searches to get listing pages not review pages
    combined_lower = " ".join(parts).lower()
    if any(w in combined_lower for w in ["car", "bike", "suv", "sedan", "motorcycle"]):
        parts.append("for sale")

    # Other constraints (fuel type, transmission, etc.) — skip seating/size for query clarity
    for c in other_constraints[:2]:
        if c.lower() not in combined_lower:
            parts.append(c)

    # City
    if city:
        parts.append(str(city).title())

    # Budget
    budget_max = intent.get("budget_max")
    if budget_max:
        if budget_max >= 10000000:   # 1 crore+
            crores = budget_max / 10000000
            parts.append(f"under {crores:.0f} crore")
        elif budget_max >= 100000:
            lakhs = budget_max / 100000
            parts.append(f"under {lakhs:.0f} lakh")
        else:
            parts.append(f"under ₹{int(budget_max)}")

    parts.append("india")

    return " ".join(p for p in parts if p)


# ── Phase 1: Google search → extract result URLs ────────────────────────────

_SKIP_DOMAINS = {
    "google.com", "youtube.com", "wikipedia.org", "facebook.com",
    "twitter.com", "instagram.com", "reddit.com", "quora.com",
    "indiamart.com", "justdial.com", "sulekha.com",  # B2B / directory
}

_PREFER_DOMAINS = [
    "amazon.in", "flipkart.com", "carwale.com", "cardekho.com",
    "cars24.com", "spinny.com", "zigwheels.com", "droom.in",
    "olx.in", "snapdeal.com", "myntra.com", "ajio.com",
]


async def _google_search_links(query: str, on_status=None, max_links: int = 3) -> list[tuple[str, str]]:
    """
    Phase 1 of the new search pipeline.
    Opens Google, searches for `query`, scrapes the organic result links from the DOM
    (no screenshot/vision needed — just link extraction).
    Returns list of (url, site_key) tuples, preferred sites first.
    """
    async def _cb(t):
        if on_status:
            try: await on_status(t)
            except Exception: pass

    search_url = f"https://www.google.com/search?q={quote_plus(query)}&gl=in&hl=en&num=10"
    await _cb("Searching Google…")

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
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
            )
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1500)

            # Extract all href links visible on the SERP
            raw_links: list[str] = await page.evaluate("""
                () => {
                    const seen = new Set();
                    const out = [];
                    const anchors = document.querySelectorAll('a[href]');
                    for (const a of anchors) {
                        let href = a.href || '';
                        // Google wraps some links in /url?q= redirects
                        try {
                            const u = new URL(href);
                            if (u.hostname === 'www.google.com' && u.pathname === '/url') {
                                href = u.searchParams.get('q') || href;
                            }
                        } catch(e) {}
                        if (!href.startsWith('http')) continue;
                        try {
                            const host = new URL(href).hostname.replace('www.', '');
                            const blocked = ['google.', 'youtube.', 'gstatic.', 'googleapis.',
                                             'wikipedia.', 'facebook.', 'twitter.', 'instagram.',
                                             'reddit.', 'quora.', 'accounts.'];
                            if (blocked.some(b => host.includes(b))) continue;
                        } catch(e) { continue; }
                        if (seen.has(href)) continue;
                        seen.add(href);
                        out.push(href);
                        if (out.length >= 10) break;
                    }
                    return out;
                }
            """)
            await browser.close()

        print(f"[browser_agent] Google returned {len(raw_links)} raw links")

        # Score: preferred domains first, then the rest
        preferred, others = [], []
        for url in raw_links:
            try:
                host = __import__('urllib.parse', fromlist=['urlparse']).urlparse(url).netloc.replace('www.', '')
            except Exception:
                host = ""
            if any(d in host for d in _PREFER_DOMAINS):
                preferred.append(url)
            else:
                others.append(url)

        ordered = preferred + others
        picked = ordered[:max_links]

        result = [(url, _detect_site(url)) for url in picked]
        print(f"[browser_agent] picked links: {[r[0] for r in result]}")
        return result

    except Exception as exc:
        print(f"[browser_agent] Google search failed: {exc}")
        return []


# ── Site routing (kept as fallback only) ────────────────────────────────────
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
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            # Wait for product cards — short timeout, proceed anyway
            selector = _WAIT_SELECTORS.get(site, "")
            if selector:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    print(f"[browser_agent] ✓ product cards detected ({site})")
                except Exception:
                    print(f"[browser_agent] selector timeout — proceeding anyway")
                    await page.wait_for_timeout(1500)
            else:
                await page.wait_for_timeout(1500)

            # ── Take 2 screenshots (top + mid scroll) ──────────────────────
            screenshots_b64 = []
            scroll_positions = [0, 900]

            for i, scroll_y in enumerate(scroll_positions):
                await _status_cb(f"Reading page — section {i + 1} of {len(scroll_positions)}…")
                await page.evaluate(f"window.scrollTo(0, {scroll_y})")
                await page.wait_for_timeout(400)
                shot = await page.screenshot(type="jpeg", quality=70, full_page=False)
                b64 = base64.b64encode(shot).decode()
                screenshots_b64.append(b64)
                print(f"[browser_agent] screenshot at scroll={scroll_y} ({len(b64)//1024}KB)")

            # ── Extract product image URLs and page links from the DOM ──────
            img_urls: list[str] = []
            product_links: list[str] = []
            page_url = page.url  # the actual URL we landed on (after redirects)
            try:
                img_sel = _IMAGE_SELECTORS.get(site, "")
                if img_sel:
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

            # page_url is the canonical URL Google sent us to — used as product link

            await browser.close()

        # ── Extract products from all screenshots IN PARALLEL ──────────────
        await _status_cb("AI vision reading products…")
        all_products: list[dict] = []
        seen_titles: set[str] = set()

        vision_tasks = [_vision_extract(b64, site) for b64 in screenshots_b64]
        results = await asyncio.gather(*vision_tasks, return_exceptions=True)

        for i, extracted in enumerate(results):
            if isinstance(extracted, Exception):
                print(f"[browser_agent] vision task {i} failed: {extracted}")
                continue
            new_count = 0
            for p in extracted:
                title_key = p.get("title", "").lower().strip()[:60]
                if title_key and title_key not in seen_titles:
                    seen_titles.add(title_key)
                    all_products.append(p)
                    new_count += 1
            print(f"[browser_agent] scroll {i}: {new_count} new products (total {len(all_products)})")

        def _is_generic_url(link: str) -> bool:
            """True if the link is a homepage or broad category root, not a specific listing."""
            try:
                from urllib.parse import urlparse
                path = urlparse(link).path.rstrip("/") or "/"
                return path in {"/", "/used", "/new", "/search", "/items", "/s", "/cars", "/bikes"} \
                    or len(path) < 5
            except Exception:
                return True

        def _title_search_url(product: dict, site: str) -> str:
            """Build a site-specific search URL from the product title — reliable fallback."""
            title = product.get("title", "").strip()
            if not title:
                return page_url
            q = quote_plus(title)
            if site == "amazon":   return f"https://www.amazon.in/s?k={q}"
            if site == "flipkart": return f"https://www.flipkart.com/search?q={q}"
            if site == "carwale":  return f"https://www.carwale.com/search/?q={q}"
            if site == "olx":      return f"https://www.olx.in/items/q-{q}"
            return f"https://www.google.com/search?q={q}"

        for i, p in enumerate(all_products):
            if i < len(img_urls) and not p.get("image_url"):
                p["image_url"] = img_urls[i]

            # URL strategy:
            # 1. page_url if it's a specific listing (e.g. carwale.com/bmw-cars/z4/)
            # 2. Title-based search URL on the same site (always relevant to the product)
            if page_url and not _is_generic_url(page_url):
                p["url"] = page_url
            else:
                p["url"] = _title_search_url(p, site)

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


def _brand_filter(products: list[dict], intent: dict) -> list[dict]:
    """
    Hard brand filter — if user specified a brand (e.g. BMW), remove every
    product that doesn't mention that brand in its title or tags.
    Returns unfiltered list only if NOTHING matched (so we never return empty-handed).
    """
    constraints = intent.get("constraints") or []
    brand = None
    for c in constraints:
        if str(c).lower().startswith("brand:"):
            brand = str(c).split(":", 1)[1].strip().lower()
            break

    # Also check category itself — "bmw car" puts brand in category
    category = (intent.get("category") or "").lower()
    _KNOWN_CAR_BRANDS = [
        "bmw", "mercedes", "audi", "volkswagen", "toyota", "honda",
        "hyundai", "maruti", "suzuki", "tata", "kia", "mahindra",
        "skoda", "jeep", "ford", "nissan", "renault", "volvo",
        "porsche", "lexus", "jaguar", "land rover",
    ]
    if not brand:
        for b in _KNOWN_CAR_BRANDS:
            if b in category:
                brand = b
                break

    if not brand:
        return products  # no brand constraint — return all

    matching = [
        p for p in products
        if brand in (p.get("title", "") + " " + " ".join(p.get("tags", []))).lower()
    ]
    print(f"[browser_agent] brand filter '{brand}': {len(products)} → {len(matching)} products")
    return matching if matching else products  # fallback to all if zero matched


async def search_products_stream(intent: dict, limit: int = 15):
    """
    Google-first search pipeline:
      1. Google the natural-language query → get top product page URLs
      2. Visit those pages in parallel → vision-extract products
      3. Merge, filter, rank
    Falls back to direct site search if Google returns no links.
    """
    query = _build_google_query(intent)
    status_q: asyncio.Queue = asyncio.Queue()

    async def on_status(text: str):
        await status_q.put(text)

    # ── Phase 1: Google search (runs in this coroutine, not a task) ───────────
    yield _status(f"Searching Google for: {query}")

    links = await _google_search_links(query, on_status=on_status, max_links=3)

    while not status_q.empty():
        yield _status(status_q.get_nowait())

    # ── If Google failed, fall back to direct site navigation ─────────────────
    if not links:
        site = _pick_site(intent)
        fallback_query = _build_query(intent)
        url = _SEARCH_URLS[site].format(query=fallback_query.replace(" ", "+"))
        site_labels = {"amazon": "Amazon.in", "flipkart": "Flipkart", "carwale": "CarWale", "olx": "OLX.in"}
        yield _status(f"Google unavailable — opening {site_labels.get(site, site)} directly…")
        links = [(url, site)]

    # ── Phase 2: visit pages in parallel ─────────────────────────────────────
    from urllib.parse import urlparse
    link_labels = [urlparse(u).netloc for u, _ in links]
    yield _status(f"Opening {len(links)} pages: {', '.join(link_labels)}…")

    browse_tasks = [
        asyncio.create_task(_browse_and_extract(url, site, on_status=on_status))
        for url, site in links
    ]

    # Hard 60s total deadline across all tasks
    deadline = asyncio.get_event_loop().time() + 60

    while not all(t.done() for t in browse_tasks):
        if asyncio.get_event_loop().time() > deadline:
            for t in browse_tasks:
                if not t.done():
                    t.cancel()
            yield _status("Pages took too long — using what we have so far…")
            break
        # Drain status queue
        try:
            text = await asyncio.wait_for(status_q.get(), timeout=0.4)
            yield _status(text)
        except asyncio.TimeoutError:
            pass

    while not status_q.empty():
        yield _status(status_q.get_nowait())

    # Collect results from all tasks
    products: list[dict] = []
    for task in browse_tasks:
        try:
            result = await task
            products.extend(result)
        except (asyncio.CancelledError, Exception):
            pass

    if products:
        yield _status(f"Found {len(products)} products across {len(links)} pages — filtering…")
        products = _sanity_filter(products, intent)
        products = _brand_filter(products, intent)

    # Budget hard filter
    budget_max = intent.get("budget_max")
    if budget_max:
        within = [p for p in products if p.get("price", float("inf")) <= budget_max]
        if within:
            products = within

    count = len(products)
    yield _status(f"{count} product{'s' if count != 1 else ''} matched — ranking by confidence…")
    yield {"type": "products", "data": products[:limit]}


async def search_products_broad_stream(intent: dict):
    """
    Broad search — strips priorities/missing_info and re-runs through the
    same Google-first pipeline with a simpler query.
    """
    loose_intent = {
        "category":   intent.get("category", ""),
        "use_case":   intent.get("use_case", ""),
        "budget_max": intent.get("budget_max"),
        "constraints": intent.get("constraints", []),
        "priorities":  [],   # drop priorities for broad search
    }
    products = []
    async for event in search_products_stream(loose_intent, limit=10):
        if event["type"] == "products":
            products = event["data"]
        else:
            yield event
    yield {"type": "products", "data": products}



async def create_cart(variant_id: str, quantity: int = 1) -> Optional[str]:
    """Not applicable for browser-sourced products."""
    return None
