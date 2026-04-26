"""
Browser Agent — ShopSense's eyes on the web.

The AI controls a real browser, navigates to product sites,
takes a screenshot, and uses Groq Vision (llama-3.2-90b-vision-preview)
to read prices, ratings, and reviews — exactly like a human would.

Sites:
  - Amazon.in      → general products
  - Flipkart.com   → general products (fallback)
  - CarWale.com    → cars / bikes / vehicles
  - OLX.in         → used / second-hand items
"""

import base64
import json
import os
import re
from typing import Optional

# ── Demo fallback data (used when live browsing fails) ──────────────────────
# Realistic products per category so the demo never dead-ends.

_DEMO_PRODUCTS: dict[str, list[dict]] = {
    "carwale": [
        {"id": "cw_1", "title": "Maruti Suzuki Swift VDi", "description": "2019 model, 45000 km driven, single owner, diesel, well maintained", "tags": ["used", "car", "daily", "hatchback", "diesel", "maruti", "swift"], "price": 480000, "rating": 4.4, "review_count": 320, "image_url": None, "variant_id": None, "source": "carwale"},
        {"id": "cw_2", "title": "Hyundai i20 Sportz Petrol", "description": "2018 model, 52000 km, second owner, petrol, good condition", "tags": ["used", "car", "daily", "hatchback", "petrol", "hyundai", "i20"], "price": 450000, "rating": 4.2, "review_count": 215, "image_url": None, "variant_id": None, "source": "carwale"},
        {"id": "cw_3", "title": "Toyota Etios Liva G", "description": "2017 model, 60000 km, first owner, petrol, clean interior", "tags": ["used", "car", "daily", "hatchback", "petrol", "toyota", "etios"], "price": 390000, "rating": 4.1, "review_count": 180, "image_url": None, "variant_id": None, "source": "carwale"},
        {"id": "cw_4", "title": "Honda Amaze S MT Petrol", "description": "2019 model, 38000 km, first owner, petrol sedan, great fuel efficiency", "tags": ["used", "car", "daily", "sedan", "petrol", "honda", "amaze"], "price": 495000, "rating": 4.5, "review_count": 290, "image_url": None, "variant_id": None, "source": "carwale"},
        {"id": "cw_5", "title": "Maruti Suzuki Alto 800 LXi", "description": "2020 model, 28000 km, first owner, petrol, city car, very economical", "tags": ["used", "car", "daily", "hatchback", "petrol", "maruti", "alto", "city"], "price": 280000, "rating": 4.0, "review_count": 410, "image_url": None, "variant_id": None, "source": "carwale"},
        {"id": "cw_6", "title": "Tata Tiago XZ Petrol", "description": "2021 model, 22000 km, first owner, petrol, safety rated, modern features", "tags": ["used", "car", "daily", "hatchback", "petrol", "tata", "tiago", "safety"], "price": 490000, "rating": 4.3, "review_count": 260, "image_url": None, "variant_id": None, "source": "carwale"},
    ],
    "olx": [
        {"id": "olx_1", "title": "iPhone 12 64GB Blue", "description": "Used 1 year, excellent condition, all accessories included, minor scratches", "tags": ["used", "iphone", "smartphone", "apple", "mobile"], "price": 28000, "rating": 4.3, "review_count": None, "image_url": None, "variant_id": None, "source": "olx"},
        {"id": "olx_2", "title": "Samsung Galaxy S21 5G", "description": "8 months old, no scratches, original box, charger included", "tags": ["used", "samsung", "smartphone", "android", "5g", "mobile"], "price": 32000, "rating": 4.1, "review_count": None, "image_url": None, "variant_id": None, "source": "olx"},
        {"id": "olx_3", "title": "OnePlus 9R 8GB/128GB", "description": "6 months old, minor wear, fast charging, gaming phone", "tags": ["used", "oneplus", "smartphone", "android", "gaming", "mobile"], "price": 22000, "rating": 4.2, "review_count": None, "image_url": None, "variant_id": None, "source": "olx"},
    ],
    "amazon": [
        {"id": "amz_1", "title": "Nike Air Max 270 Running Shoes", "description": "Lightweight road running shoe with Max Air cushioning, breathable mesh upper", "tags": ["running", "shoes", "road", "cushioned", "lightweight", "nike"], "price": 7495, "rating": 4.4, "review_count": 12500, "image_url": None, "variant_id": None, "source": "amazon"},
        {"id": "amz_2", "title": "Adidas Ultraboost 22 Road Running", "description": "Responsive Boost midsole, Primeknit+ upper, ideal for daily road training", "tags": ["running", "shoes", "road", "boost", "adidas", "daily"], "price": 9999, "rating": 4.6, "review_count": 8300, "image_url": None, "variant_id": None, "source": "amazon"},
        {"id": "amz_3", "title": "Puma Voyage Nitro Trail Shoes", "description": "Trail running shoe with Nitro foam, strong grip outsole, waterproof", "tags": ["running", "shoes", "trail", "grip", "puma", "waterproof"], "price": 5999, "rating": 4.3, "review_count": 4200, "image_url": None, "variant_id": None, "source": "amazon"},
        {"id": "amz_4", "title": "Skechers Go Run 7 Hyper", "description": "Ultra-lightweight everyday trainer, shock-absorbing, wide toe box, flat feet friendly", "tags": ["running", "shoes", "road", "lightweight", "flat feet", "skechers", "daily"], "price": 3999, "rating": 4.2, "review_count": 6700, "image_url": None, "variant_id": None, "source": "amazon"},
        {"id": "amz_5", "title": "Lakme 9to5 Primer Matte Lip", "description": "Long stay matte lipstick, moisturising formula, 16hr wear", "tags": ["lipstick", "matte", "makeup", "lakme", "longlasting"], "price": 349, "rating": 4.1, "review_count": 22000, "image_url": None, "variant_id": None, "source": "amazon"},
        {"id": "amz_6", "title": "Neutrogena Oil-Free Moisturiser SPF 15", "description": "Lightweight daily moisturiser for oily skin, non-comedogenic, SPF protection", "tags": ["skincare", "moisturiser", "oily skin", "spf", "neutrogena", "daily"], "price": 799, "rating": 4.5, "review_count": 31000, "image_url": None, "variant_id": None, "source": "amazon"},
        {"id": "amz_7", "title": "Redmi Note 12 Pro 5G 8GB/128GB", "description": "108MP camera, 5000mAh battery, AMOLED display, fast charging", "tags": ["smartphone", "android", "5g", "camera", "redmi", "xiaomi"], "price": 18999, "rating": 4.3, "review_count": 45000, "image_url": None, "variant_id": None, "source": "amazon"},
        {"id": "amz_8", "title": "Samsung Galaxy M34 5G 6GB/128GB", "description": "6000mAh battery, 50MP camera, 5G ready, water-resistant", "tags": ["smartphone", "android", "5g", "battery", "samsung", "camera"], "price": 15999, "rating": 4.4, "review_count": 38000, "image_url": None, "variant_id": None, "source": "amazon"},
    ],
    "flipkart": [
        {"id": "fk_1", "title": "boAt Rockerz 450 Bluetooth Headphone", "description": "40hr playtime, 40mm drivers, foldable design, mic included", "tags": ["headphone", "bluetooth", "wireless", "boat", "music"], "price": 1299, "rating": 4.1, "review_count": 95000, "image_url": None, "variant_id": None, "source": "flipkart"},
        {"id": "fk_2", "title": "Fastrack Analog Watch for Men", "description": "Casual analog watch, water resistant 30m, leather strap", "tags": ["watch", "analog", "casual", "fastrack", "men"], "price": 1195, "rating": 4.0, "review_count": 12000, "image_url": None, "variant_id": None, "source": "flipkart"},
    ],
}

from openai import AsyncOpenAI
from playwright.async_api import async_playwright

_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

_VISION_MODEL = "llama-3.2-90b-vision-preview"

# ── Search URL templates ────────────────────────────────────────────────────

_SEARCH_URLS = {
    "amazon":   "https://www.amazon.in/s?k={query}",
    "flipkart": "https://www.flipkart.com/search?q={query}",
    "carwale":  "https://www.carwale.com/new-cars/?q={query}",
    "olx":      "https://www.olx.in/items/q-{query}",
}

# ── Vision extraction prompt ────────────────────────────────────────────────

_EXTRACT_PROMPT = """You are looking at a product search results page screenshot.

Extract every visible product listing. For each one return:
- title: exact product name as shown
- price: price in INR as a plain number (e.g. 1299, not "₹1,299"). If a range, use the lower number.
- rating: star rating out of 5 as a decimal if visible (e.g. 4.3), else null
- review_count: number of ratings/reviews if visible as an integer, else null
- description: any visible highlights, specs, or tagline (1-2 sentences max)
- tags: list of relevant keywords extracted from title and description

Return ONLY a valid JSON array, nothing else:
[
  {
    "title": "...",
    "price": 1299,
    "rating": 4.3,
    "review_count": 1500,
    "description": "...",
    "tags": ["tag1", "tag2"]
  }
]

Rules:
- Skip any product where price is not visible or is 0
- Include ALL visible products, even if some fields are null
- Do not add commentary, just the JSON array
"""


# ── Site routing ────────────────────────────────────────────────────────────

def _pick_site(intent: dict) -> str:
    combined = (
        (intent.get("category") or "") + " " +
        (intent.get("use_case") or "")
    ).lower()

    if any(w in combined for w in ["car", "bike", "motorcycle", "suv", "sedan", "hatchback", "vehicle"]):
        return "carwale"
    if any(w in combined for w in ["used", "second hand", "secondhand", "pre-owned", "old", "refurbished"]):
        return "olx"
    return "amazon"


def _build_query(intent: dict) -> str:
    parts = [p for p in [
        intent.get("category"),
        intent.get("use_case"),
    ] if p]
    return " ".join(parts) if parts else "products"


# ── Browser + screenshot ────────────────────────────────────────────────────

async def _get_screenshot_b64(url: str) -> Optional[str]:
    """Launch a real browser, load the URL, return a base64 JPEG screenshot."""
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2500)   # let JS / lazy-load settle

            # Scroll down a little to trigger lazy-loaded product cards
            await page.evaluate("window.scrollBy(0, 400)")
            await page.wait_for_timeout(500)

            screenshot_bytes = await page.screenshot(type="jpeg", quality=72, full_page=False)
            await browser.close()

        return base64.b64encode(screenshot_bytes).decode()

    except Exception as exc:
        print(f"[browser_agent] screenshot error: {exc}")
        return None


# ── Vision extraction ───────────────────────────────────────────────────────

async def _vision_extract(screenshot_b64: str, site: str) -> list[dict]:
    """Send screenshot to Groq Vision and parse product list."""
    try:
        response = await _client.chat.completions.create(
            model=_VISION_MODEL,
            max_tokens=2000,
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
                            "text": _EXTRACT_PROMPT,
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


async def search_products_stream(intent: dict, limit: int = 15):
    """
    Async generator — yields status dicts then a final products dict.
    Use in main.py to stream live status to the frontend.
    """
    site = _pick_site(intent)
    query = _build_query(intent)
    site_labels = {"amazon": "Amazon.in", "flipkart": "Flipkart", "carwale": "CarWale", "olx": "OLX.in"}
    label = site_labels.get(site, site)
    url = _SEARCH_URLS[site].format(query=query.replace(" ", "+"))

    yield _status(f"Opening {label}…")
    screenshot_b64 = await _get_screenshot_b64(url)

    products = []

    if screenshot_b64:
        yield _status(f"Screenshot taken — reading with AI vision…")
        products = await _vision_extract(screenshot_b64, site)

    # Fallback to demo data if live browsing failed or returned nothing
    if not products:
        yield _status(f"Using curated listings for {label}…")
        products = _get_demo_products(site, intent)

    budget_max = intent.get("budget_max")
    if budget_max:
        products = [p for p in products if p["price"] <= budget_max]

    count = len(products)
    yield _status(f"Found {count} product{'s' if count != 1 else ''} — ranking by confidence…")
    yield {"type": "products", "data": products[:limit]}


async def search_products_broad_stream(intent: dict):
    """Broad fallback — also yields status events."""
    site = _pick_site(intent)
    fallback_site = "flipkart" if site == "amazon" else "amazon"
    site_labels = {"amazon": "Amazon.in", "flipkart": "Flipkart", "carwale": "CarWale", "olx": "OLX.in"}

    loose_intent = {"category": intent.get("category", "")}
    products = []

    async for event in search_products_stream(loose_intent, limit=10):
        if event["type"] == "products":
            products = event["data"]
        else:
            yield event

    if not products:
        label = site_labels.get(fallback_site, fallback_site)
        yield _status(f"Trying {label} instead…")
        query = _build_query(loose_intent)
        url = _SEARCH_URLS[fallback_site].format(query=query.replace(" ", "+"))
        screenshot_b64 = await _get_screenshot_b64(url)
        if screenshot_b64:
            products = await _vision_extract(screenshot_b64, fallback_site)

    yield {"type": "products", "data": products}


def _get_demo_products(site: str, intent: dict) -> list[dict]:
    """Return curated demo products filtered loosely by intent when live browsing fails."""
    pool = list(_DEMO_PRODUCTS.get(site, _DEMO_PRODUCTS["amazon"]))

    # Light keyword filter so demo products feel relevant
    category = (intent.get("category") or "").lower()
    use_case = (intent.get("use_case") or "").lower()
    keywords = [w for w in (category + " " + use_case).split() if len(w) > 2]

    if keywords:
        scored = []
        for p in pool:
            text = (p["title"] + " " + " ".join(p["tags"])).lower()
            hits = sum(1 for k in keywords if k in text)
            scored.append((hits, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Return top matches; fall back to full pool if nothing matched
        filtered = [p for hits, p in scored if hits > 0]
        pool = filtered if filtered else pool

    return pool


async def create_cart(variant_id: str, quantity: int = 1) -> Optional[str]:
    """Not applicable for browser-sourced products."""
    return None
