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


# ── Public API (same shape as shopify_client) ───────────────────────────────

async def search_products(intent: dict, limit: int = 15) -> list[dict]:
    """Browse the best site for the intent, screenshot it, extract products via AI vision."""
    site = _pick_site(intent)
    query = _build_query(intent)
    url = _SEARCH_URLS[site].format(query=query.replace(" ", "+"))

    print(f"[browser_agent] browsing {site}: {url}")

    screenshot_b64 = await _get_screenshot_b64(url)
    if not screenshot_b64:
        return []

    products = await _vision_extract(screenshot_b64, site)

    # Filter by budget
    budget_max = intent.get("budget_max")
    if budget_max:
        products = [p for p in products if p["price"] <= budget_max]

    print(f"[browser_agent] extracted {len(products)} products from {site}")
    return products[:limit]


async def search_products_broad(intent: dict) -> list[dict]:
    """Fallback: drop constraints, try Flipkart if Amazon failed."""
    site = _pick_site(intent)
    fallback_site = "flipkart" if site == "amazon" else "amazon"

    loose_intent = {"category": intent.get("category", "")}

    # Try original site first, then fallback
    products = await search_products(loose_intent, limit=10)
    if not products:
        query = _build_query(loose_intent)
        url = _SEARCH_URLS[fallback_site].format(query=query.replace(" ", "+"))
        print(f"[browser_agent] broad fallback → {fallback_site}")
        screenshot_b64 = await _get_screenshot_b64(url)
        if screenshot_b64:
            products = await _vision_extract(screenshot_b64, fallback_site)

    return products


async def create_cart(variant_id: str, quantity: int = 1) -> Optional[str]:
    """Not applicable for browser-sourced products."""
    return None
