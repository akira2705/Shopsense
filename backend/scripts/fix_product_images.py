"""
fix_product_images.py — Replace wrong/placeholder images with real product images.

Strategy per product:
  1. Search Amazon.in for the exact model name → grab main product image
  2. Fallback: search Flipkart
  3. Fallback: search brand website directly
  4. Skip if all fail (don't leave placeholder worse than none)

Shopify:
  • DELETE existing image(s) first
  • POST new image via REST products/{id}/images.json

Usage:
    cd backend
    python scripts/fix_product_images.py

    # Only process products whose images are missing or are placeholders:
    python scripts/fix_product_images.py --missing-only

    # Dry run (print what it would do):
    python scripts/fix_product_images.py --dry-run
"""

import argparse
import asyncio
import json
import os
import sys
from urllib.parse import quote_plus

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

load_dotenv()

# ─── Config ─────────────────────────────────────────────────────────────────────

def _first_env(*names: str) -> str:
    for name in names:
        v = os.getenv(name, "").strip()
        if v:
            return v
    return ""

def _norm_domain(v: str) -> str:
    v = v.strip().rstrip("/")
    v = v.removeprefix("https://").removeprefix("http://")
    return v.split("/", 1)[0]

STORE        = _norm_domain(_first_env("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN"))
TOKEN        = _first_env("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_ADMIN_ACCESS_TOKEN")
API_VER      = "2024-01"
BASE         = f"https://{STORE}/admin/api/{API_VER}"
HEADERS      = {"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN}

PLACEHOLDER_MARKERS = ["placehold.co", "placeholder", "via.placeholder"]

# ─── Shopify REST helpers ────────────────────────────────────────────────────────

async def shopify_get(client: httpx.AsyncClient, path: str) -> dict:
    r = await client.get(f"{BASE}{path}", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

async def shopify_post(client: httpx.AsyncClient, path: str, body: dict) -> dict:
    r = await client.post(f"{BASE}{path}", headers=HEADERS, json=body, timeout=20)
    r.raise_for_status()
    return r.json()

async def shopify_delete(client: httpx.AsyncClient, path: str) -> None:
    r = await client.delete(f"{BASE}{path}", headers=HEADERS, timeout=20)
    r.raise_for_status()


async def get_all_products(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all products with their numeric IDs and current images."""
    products = []
    page_info = None
    limit = 100

    while True:
        params = f"?limit={limit}&fields=id,title,vendor,product_type,images"
        if page_info:
            params += f"&page_info={page_info}"
        r = await client.get(f"{BASE}/products.json{params}", headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        batch = data.get("products", [])
        products.extend(batch)

        # Parse next page from Link header
        link = r.headers.get("Link", "")
        if 'rel="next"' in link:
            # Extract page_info token
            for part in link.split(","):
                if 'rel="next"' in part:
                    url_part = part.split(";")[0].strip().strip("<>")
                    for param in url_part.split("&"):
                        if param.startswith("page_info="):
                            page_info = param.split("=", 1)[1]
                            break
                    break
        else:
            break

    return products


async def delete_product_images(client: httpx.AsyncClient, product_id: int, image_ids: list[int]) -> None:
    for img_id in image_ids:
        try:
            await shopify_delete(client, f"/products/{product_id}/images/{img_id}.json")
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"    ⚠  Could not delete image {img_id}: {e}")


async def upload_image(client: httpx.AsyncClient, product_id: int, image_url: str, alt: str) -> bool:
    try:
        data = await shopify_post(
            client,
            f"/products/{product_id}/images.json",
            {"image": {"src": image_url, "alt": alt}}
        )
        img = data.get("image", {})
        return bool(img.get("id"))
    except Exception as e:
        print(f"    ✗  Upload failed: {e}")
        return False


# ─── Image search via Playwright ────────────────────────────────────────────────

async def _wait_for_selector(page: Page, selector: str, timeout: int = 8000):
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return True
    except PWTimeout:
        return False


async def search_amazon(page: Page, title: str, vendor: str) -> str | None:
    """
    Search Amazon.in for the product, click the first result, get the main image.
    Returns a high-res image URL or None.
    """
    query = f"{title} {vendor}".strip()
    url = f"https://www.amazon.in/s?k={quote_plus(query)}"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)

        # Wait for search results
        if not await _wait_for_selector(page, "[data-component-type='s-search-result']", 10000):
            return None

        # Get the first non-sponsored result's link
        results = await page.query_selector_all("[data-component-type='s-search-result']")
        product_url = None
        for result in results[:5]:
            # Skip sponsored results
            sponsored = await result.query_selector(".puis-sponsored-label-text")
            if sponsored:
                continue
            link = await result.query_selector("h2 a")
            if link:
                href = await link.get_attribute("href")
                if href:
                    product_url = "https://www.amazon.in" + href if href.startswith("/") else href
                    break

        if not product_url:
            # Fallback: take first result regardless of sponsored
            first = results[0] if results else None
            if first:
                link = await first.query_selector("h2 a")
                if link:
                    href = await link.get_attribute("href")
                    if href:
                        product_url = "https://www.amazon.in" + href if href.startswith("/") else href

        if not product_url:
            return None

        # Navigate to product page
        await page.goto(product_url, wait_until="domcontentloaded", timeout=20000)

        # Try multiple image selectors — Amazon layout varies
        for selector in [
            "#landingImage",
            "#imgTagWrapperId img",
            "#main-image",
            ".a-dynamic-image",
            "#imageBlock img",
        ]:
            img = await page.query_selector(selector)
            if img:
                # Try data-old-hires (full res) first, then src
                src = await img.get_attribute("data-old-hires")
                if not src:
                    src = await img.get_attribute("data-a-dynamic-image")
                    if src:
                        try:
                            # data-a-dynamic-image is a JSON dict of {url: [w,h]}
                            url_dict = json.loads(src)
                            if url_dict:
                                # Pick highest resolution
                                src = max(url_dict.keys(), key=lambda u: url_dict[u][0] * url_dict[u][1])
                        except Exception:
                            src = None
                if not src:
                    src = await img.get_attribute("src")
                if src and src.startswith("http") and "gif" not in src and "pixel" not in src:
                    # Make sure it's a real image URL, not a 1x1 pixel
                    return src

        return None

    except Exception as e:
        print(f"    [Amazon] error: {e}")
        return None


async def search_flipkart(page: Page, title: str) -> str | None:
    """Search Flipkart and return the main product image from the first result."""
    query = quote_plus(title)
    url = f"https://www.flipkart.com/search?q={query}"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)

        # Dismiss login popup if it appears
        try:
            close_btn = await page.wait_for_selector("button._2KpZ6l._2doB4z", timeout=3000)
            await close_btn.click()
        except PWTimeout:
            pass

        # Get first product result
        if not await _wait_for_selector(page, "div[data-id], ._1AtVbE", 8000):
            return None

        # Click first product
        link = await page.query_selector("a._1fQZEK, a.s1Q9rs, ._2rpwqI a, ._4rR01T")
        if not link:
            return None

        href = await link.get_attribute("href")
        if not href:
            return None

        prod_url = "https://www.flipkart.com" + href if href.startswith("/") else href
        await page.goto(prod_url, wait_until="domcontentloaded", timeout=20000)

        # Get main image
        for selector in ["._396cs4 img", "._2r_T1I img", ".CXW8mj img", "img._2amPTt"]:
            img = await page.query_selector(selector)
            if img:
                src = await img.get_attribute("src")
                if src and src.startswith("http"):
                    # Flipkart: replace small size param with large
                    src = src.replace("/128/128/", "/832/832/").replace("/64/64/", "/832/832/")
                    return src

        return None

    except Exception as e:
        print(f"    [Flipkart] error: {e}")
        return None


# Targeted brand website scrapers for highest-quality images

BRAND_SCRAPERS: dict[str, str] = {
    "Nike":        "https://www.nike.com/in/w?q={query}",
    "Adidas":      "https://www.adidas.co.in/search?q={query}",
    "Sony":        "https://www.amazon.in/s?k={query}+sony",
    "Samsung":     "https://www.amazon.in/s?k={query}+samsung",
    "Apple":       "https://www.amazon.in/s?k={query}+apple",
    "OnePlus":     "https://www.amazon.in/s?k={query}+oneplus",
    "Xiaomi":      "https://www.amazon.in/s?k={query}+xiaomi",
    "Bose":        "https://www.amazon.in/s?k={query}+bose",
    "JBL":         "https://www.amazon.in/s?k={query}+jbl",
    "Sennheiser":  "https://www.amazon.in/s?k={query}+sennheiser",
}


async def find_image(page: Page, title: str, vendor: str, product_type: str) -> str | None:
    """
    Try multiple sources in order of preference.
    Returns first non-None image URL found.
    """
    print(f"    🔍 Searching for: {title[:60]}")

    # 1. Amazon.in — most reliable, has all brands, white-bg product shots
    img = await search_amazon(page, title, vendor)
    if img:
        print(f"    ✓  Amazon: {img[:80]}…")
        return img

    # 2. Flipkart fallback
    print(f"    → Amazon failed, trying Flipkart…")
    img = await search_flipkart(page, title)
    if img:
        print(f"    ✓  Flipkart: {img[:80]}…")
        return img

    print(f"    ✗  No image found")
    return None


# ─── Main ────────────────────────────────────────────────────────────────────────

def _is_placeholder(url: str) -> bool:
    if not url:
        return True
    return any(marker in url.lower() for marker in PLACEHOLDER_MARKERS)


async def main(missing_only: bool = False, dry_run: bool = False) -> None:
    if not STORE or not TOKEN:
        print("ERROR: Set SHOPIFY_STORE_URL and SHOPIFY_ADMIN_TOKEN in backend/.env")
        sys.exit(1)

    print(f"🛍  Store: {STORE}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Fetching all products…\n")

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        products = await get_all_products(http_client)

    print(f"Total products: {len(products)}")

    # Determine which need fixing
    to_fix = []
    for p in products:
        images = p.get("images", [])
        if not images:
            to_fix.append((p, []))    # no image at all
        else:
            # Check if any image is a placeholder
            has_bad = any(_is_placeholder(img.get("src", "")) for img in images)
            if missing_only and not has_bad and images:
                continue     # already has a real image, skip in missing-only mode
            image_ids = [img["id"] for img in images]
            if has_bad or not missing_only:
                to_fix.append((p, image_ids))

    print(f"Products to fix: {len(to_fix)}\n")

    if not to_fix:
        print("✅ Nothing to do!")
        return

    fixed = 0
    failed = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-IN",
        )
        page = await context.new_page()

        # Block unnecessary resources for speed
        await page.route(
            "**/*.{woff,woff2,pdf,mp4,webm}",
            lambda r: r.abort()
        )

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            for i, (product, old_image_ids) in enumerate(to_fix, 1):
                pid     = product["id"]
                title   = product["title"]
                vendor  = product.get("vendor", "")
                ptype   = product.get("product_type", "")

                print(f"\n[{i:02d}/{len(to_fix)}] {title}")

                if dry_run:
                    print(f"    [dry-run] would search and replace image")
                    continue

                # Find image
                image_url = await find_image(page, title, vendor, ptype)
                if not image_url:
                    failed += 1
                    continue

                # Delete old images
                if old_image_ids:
                    await delete_product_images(http_client, pid, old_image_ids)
                    await asyncio.sleep(0.5)

                # Upload new image
                ok = await upload_image(http_client, pid, image_url, title)
                if ok:
                    print(f"    ✅ Updated image for: {title}")
                    fixed += 1
                else:
                    failed += 1

                # Be gentle with Shopify rate limits
                await asyncio.sleep(0.8)

        await browser.close()

    print(f"\n{'─'*55}")
    print(f"✅  Fixed: {fixed}   ✗ Failed: {failed}   / {len(to_fix)} total")
    if failed > 0:
        print("\nFailed products still need images — check output above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix Shopify product images")
    parser.add_argument("--missing-only", action="store_true",
                        help="Only fix products with placeholder/missing images (skip real images)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without making any changes")
    args = parser.parse_args()

    asyncio.run(main(missing_only=args.missing_only, dry_run=args.dry_run))
