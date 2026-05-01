"""
upload_images_google.py — Upload correct product images using Google Custom Search API.

Setup (free, 2 min):
  1. https://console.cloud.google.com → create project → enable "Custom Search API" → create API key
  2. https://cse.google.com/cse/create/new → "Search entire web" → get CX (Search Engine ID)
  3. Add to backend/.env:
       GOOGLE_API_KEY=AIza...
       GOOGLE_CX=a1b2c3...

Usage:
    cd backend
    py scripts/upload_images_google.py
    py scripts/upload_images_google.py --dry-run    # preview without uploading
    py scripts/upload_images_google.py --start 50   # resume from product #50
"""

import argparse
import asyncio
import os
import sys
import time
from urllib.parse import quote_plus

import httpx
from dotenv import load_dotenv

load_dotenv()

# ─── Config ─────────────────────────────────────────────────────────────────────

def _first_env(*names):
    for n in names:
        v = os.getenv(n, "").strip()
        if v: return v
    return ""

def _norm(v):
    v = v.strip().rstrip("/").removeprefix("https://").removeprefix("http://")
    return v.split("/", 1)[0]

STORE        = _norm(_first_env("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN"))
TOKEN        = _first_env("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_ADMIN_ACCESS_TOKEN")
GOOGLE_KEY   = _first_env("GOOGLE_API_KEY")
GOOGLE_CX    = _first_env("GOOGLE_CX")

BASE         = f"https://{STORE}/admin/api/2024-01"
SHOP_HEADERS = {"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN}

# Domains to prefer for product images (brand official + major retailers)
PREFERRED_DOMAINS = (
    "nike.com", "adidas.co.in", "adidas.com",
    "sony.co.in", "samsung.com",
    "apple.com", "oneplus.com", "mi.com",
    "bose.com", "jbl.com", "sennheiser.com",
    "amazon.in", "flipkart.com",
    "myntra.com", "nykaa.com",
    "maruti.co.in", "hyundai.co.in", "tatamotors.com",
    "kia.com", "mg.co.in",
)

# Bad image sources (logos, icons, placeholder, small thumbnails)
BLOCKED_DOMAINS = ("1x1", "pixel", "placeholder", "logo", "icon", "favicon", "badge")


# ─── Google Image Search ─────────────────────────────────────────────────────────

async def google_image_search(client: httpx.AsyncClient, query: str) -> str | None:
    """
    Search Google Custom Search API for an image matching query.
    Returns the best matching image URL or None.
    API docs: https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key":        GOOGLE_KEY,
        "cx":         GOOGLE_CX,
        "q":          query,
        "searchType": "image",
        "num":        5,          # get 5 candidates, pick best
        "imgSize":    "large",    # prefer large images
        "imgType":    "photo",    # real photos, not clipart
        "safe":       "active",
    }

    try:
        r = await client.get(url, params=params, timeout=15)
        if r.status_code == 429:
            print("    [Google] rate limited — waiting 60s")
            await asyncio.sleep(60)
            r = await client.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        items = data.get("items", [])
        if not items:
            return None

        # Score each result — prefer official brand sites
        def score(item):
            link = item.get("link", "").lower()
            display = item.get("displayLink", "").lower()
            s = 0
            for domain in PREFERRED_DOMAINS:
                if domain in display or domain in link:
                    s += 10
                    break
            for bad in BLOCKED_DOMAINS:
                if bad in link:
                    s -= 20
            # Prefer larger images
            meta = item.get("image", {})
            w = meta.get("width", 0)
            h = meta.get("height", 0)
            if w >= 500 and h >= 500:
                s += 5
            if w >= 800 and h >= 800:
                s += 5
            return s

        best = max(items, key=score)
        img_url = best.get("link")

        # Filter out bad URLs
        if not img_url or not img_url.startswith("http"):
            return None
        if any(b in img_url.lower() for b in BLOCKED_DOMAINS):
            return None

        return img_url

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            print(f"    [Google] 403 — check API key and quota")
        else:
            print(f"    [Google] HTTP {e.response.status_code}")
        return None
    except Exception as e:
        print(f"    [Google] error: {e}")
        return None


def _build_query(title: str, vendor: str, product_type: str) -> str:
    """Build a targeted image search query for the exact product."""
    # Strip internal tier suffixes your friend added (Value/Plus/Pro/Elite/Ultra/Everyday)
    clean = title
    for suffix in [" Value", " Plus", " Pro", " Elite", " Ultra", " Everyday", " Legend"]:
        clean = clean.replace(suffix, "")
    clean = clean.strip()

    # For cars: search manufacturer site
    if product_type and "car" in product_type.lower():
        return f"{clean} official car India"

    # For shoes: white background product shot
    if product_type and "shoe" in product_type.lower():
        return f"{clean} product image white background"

    # Default: exact model name, product shot
    if vendor and vendor.lower() not in clean.lower():
        return f"{vendor} {clean} product image"
    return f"{clean} product image"


# ─── Shopify helpers ─────────────────────────────────────────────────────────────

async def get_all_products(client: httpx.AsyncClient) -> list[dict]:
    products = []
    page_info = None
    while True:
        url = f"{BASE}/products.json?limit=250&fields=id,title,vendor,product_type,images"
        if page_info:
            url += f"&page_info={page_info}"
        r = await client.get(url, headers=SHOP_HEADERS)
        r.raise_for_status()
        products.extend(r.json().get("products", []))
        link = r.headers.get("Link", "")
        if 'rel="next"' in link:
            for part in link.split(","):
                if 'rel="next"' in part:
                    for param in part.split(";")[0].strip().strip("<>").split("&"):
                        if param.startswith("page_info="):
                            page_info = param.split("=", 1)[1]
                            break
                    break
        else:
            break
    return products


async def upload_image(client: httpx.AsyncClient, product_id: int, img_url: str, alt: str) -> bool:
    try:
        r = await client.post(
            f"{BASE}/products/{product_id}/images.json",
            headers=SHOP_HEADERS,
            json={"image": {"src": img_url, "alt": alt}},
            timeout=20,
        )
        r.raise_for_status()
        return bool(r.json().get("image", {}).get("id"))
    except Exception as e:
        print(f"    [Shopify] upload failed: {e}")
        return False


# ─── Main ────────────────────────────────────────────────────────────────────────

async def main(dry_run: bool = False, start_at: int = 0) -> None:
    if not STORE or not TOKEN:
        print("ERROR: Set SHOPIFY_STORE_URL + SHOPIFY_ADMIN_TOKEN in backend/.env")
        sys.exit(1)
    if not GOOGLE_KEY or not GOOGLE_CX:
        print("ERROR: Set GOOGLE_API_KEY + GOOGLE_CX in backend/.env")
        print()
        print("Setup (free, 2 min):")
        print("  1. https://console.cloud.google.com -> enable Custom Search API -> create API key")
        print("  2. https://cse.google.com/cse/create/new -> Search entire web -> copy CX")
        print("  3. Add to backend/.env:")
        print("       GOOGLE_API_KEY=AIza...")
        print("       GOOGLE_CX=a1b2c3...")
        sys.exit(1)

    print(f"Store: {STORE}")
    print(f"{'[DRY RUN] ' if dry_run else ''}Fetching products...")

    async with httpx.AsyncClient(timeout=30) as client:
        products = await get_all_products(client)

    # Only process products without images (or all if start_at > 0)
    to_fix = [p for p in products if not p.get("images")]
    if start_at:
        to_fix = products[start_at:]

    print(f"Products without images: {len(to_fix)} / {len(products)}")
    if not to_fix:
        print("Nothing to do — all products already have images.")
        return

    fixed = 0
    failed = 0
    quota_used = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for i, p in enumerate(to_fix, 1):
            pid   = p["id"]
            title = p["title"]
            vendor = p.get("vendor", "")
            ptype  = p.get("product_type", "")

            query = _build_query(title, vendor, ptype)
            print(f"\n[{i:02d}/{len(to_fix)}] {title}")
            print(f"    query: {query}")

            if dry_run:
                print("    [dry-run] would search Google Images and upload")
                continue

            img_url = await google_image_search(client, query)
            quota_used += 1

            if not img_url:
                print(f"    FAIL no image found")
                failed += 1
            else:
                print(f"    found: {img_url[:90]}")
                ok = await upload_image(client, pid, img_url, title)
                if ok:
                    print(f"    OK uploaded")
                    fixed += 1
                else:
                    failed += 1

            # Google free tier: 100 queries/day. Stay well under rate limit.
            await asyncio.sleep(1.0)

            # Shopify rate limit: ~2 req/s
            # (we're doing 1 Shopify write per loop, fine)

    print(f"\n{'-'*55}")
    print(f"Fixed: {fixed}   Failed: {failed}   Google queries used: {quota_used}")
    if quota_used >= 95:
        print("WARNING: near Google daily quota (100/day). Run again tomorrow for remaining.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start", type=int, default=0, help="Resume from product index N")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, start_at=args.start))
