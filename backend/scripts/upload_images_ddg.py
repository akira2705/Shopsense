"""
upload_images_ddg.py — Upload product images using DuckDuckGo Image Search.

No API key needed. No daily quota.

Usage:
    cd backend
    py -u scripts/upload_images_ddg.py
    py -u scripts/upload_images_ddg.py --dry-run    # preview without uploading
    py -u scripts/upload_images_ddg.py --start 50   # resume from product #50
"""

import argparse
import asyncio
import os
import sys
import time

import httpx
from dotenv import load_dotenv
from ddgs import DDGS

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────

def _first_env(*names):
    for n in names:
        v = os.getenv(n, "").strip()
        if v:
            return v
    return ""

def _norm(v):
    v = v.strip().rstrip("/").removeprefix("https://").removeprefix("http://")
    return v.split("/", 1)[0]

STORE        = _norm(_first_env("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN"))
TOKEN        = _first_env("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_ADMIN_ACCESS_TOKEN")
BASE         = f"https://{STORE}/admin/api/2024-01"
SHOP_HEADERS = {"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN}

# Prefer official brand and major retailer domains
PREFERRED_DOMAINS = (
    "nike.com", "adidas.co.in", "adidas.com",
    "sony.co.in", "samsung.com", "apple.com",
    "oneplus.com", "mi.com", "realme.com",
    "bose.com", "jbl.com", "sennheiser.com",
    "amazon.in", "flipkart.com", "myntra.com",
    "maruti.co.in", "hyundai.co.in", "tatamotors.com",
    "kia.com", "mg.co.in",
)

BLOCKED_TERMS = ("1x1", "pixel", "placeholder", "logo", "icon", "favicon",
                 "badge", "spinner", "loading", "avatar", "profile")


# ─── DuckDuckGo Image Search ─────────────────────────────────────────────────

# Single shared session — avoids per-query bot detection
_DDGS = DDGS()

def ddg_image_search(query: str) -> list[str]:
    """Search DuckDuckGo Images, return ranked list of candidate URLs."""
    for attempt in range(3):
        try:
            results = _DDGS.images(
                query=query,
                max_results=10,
                size="Large",
            )
            if not results:
                return []

            def score(item):
                link = item.get("image", "").lower()
                source = item.get("url", "").lower()
                s = 0
                for domain in PREFERRED_DOMAINS:
                    if domain in source or domain in link:
                        s += 10
                        break
                for bad in BLOCKED_TERMS:
                    if bad in link:
                        s -= 20
                w = int(item.get("width", 0) or 0)
                h = int(item.get("height", 0) or 0)
                if w >= 500 and h >= 500:
                    s += 5
                if w >= 800 and h >= 800:
                    s += 5
                return s

            ranked = sorted(results, key=score, reverse=True)
            candidates = []
            for item in ranked:
                url = item.get("image", "")
                if url and url.startswith("http") and not any(b in url.lower() for b in BLOCKED_TERMS):
                    candidates.append(url)
            return candidates

        except Exception as e:
            err = str(e)
            if "Ratelimit" in err or "403" in err:
                wait = 10 * (attempt + 1)
                print(f"    [DDG] rate limited — waiting {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)
            else:
                print(f"    [DDG] error: {e}")
                return []

    print("    [DDG] gave up after 3 retries")
    return None


def _build_query(title: str, vendor: str, product_type: str) -> str:
    """Build a targeted image search query for the exact product."""
    clean = title.strip()

    import re
    pt = product_type.lower() if product_type else ""

    # Word-boundary match — avoids "skincare" matching "car"
    if re.search(r'\bcar\b', pt):
        return f"{clean} car exterior front view"

    if "shoe" in pt or "footwear" in pt or "sneaker" in pt:
        return f"{clean} shoe product image white background"

    if "skincare" in pt or "beauty" in pt or "serum" in pt or "cream" in pt:
        return f"{clean} product image"

    if vendor and vendor.lower() not in clean.lower():
        return f"{vendor} {clean} product image"

    return f"{clean} product image"


# ─── Shopify helpers ──────────────────────────────────────────────────────────

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


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main(dry_run: bool = False, start_at: int = 0) -> None:
    if not STORE or not TOKEN:
        print("ERROR: Set SHOPIFY_STORE_URL + SHOPIFY_ADMIN_TOKEN in backend/.env")
        sys.exit(1)

    print(f"Store: {STORE}")
    if not dry_run:
        print("Waiting 30s for DDG rate limit to cool off...")
        time.sleep(30)
    print(f"{'[DRY RUN] ' if dry_run else ''}Fetching products...")

    async with httpx.AsyncClient(timeout=30) as client:
        products = await get_all_products(client)

    to_fix = [p for p in products if not p.get("images")]
    if start_at:
        to_fix = products[start_at:]

    print(f"Products without images: {len(to_fix)} / {len(products)}\n")
    if not to_fix:
        print("Nothing to do — all products already have images.")
        return

    fixed = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for i, p in enumerate(to_fix, 1):
            pid    = p["id"]
            title  = p["title"]
            vendor = p.get("vendor", "")
            ptype  = p.get("product_type", "")

            query = _build_query(title, vendor, ptype)
            print(f"[{i:03d}/{len(to_fix)}] {title}")
            print(f"    query: {query}")

            if dry_run:
                print("    [dry-run] would search DDG and upload")
                continue

            candidates = ddg_image_search(query)

            if not candidates:
                print(f"    FAIL no image found")
                failed += 1
            else:
                uploaded = False
                for img_url in candidates:
                    print(f"    trying: {img_url[:90]}")
                    ok = await upload_image(client, pid, img_url, title)
                    if ok:
                        print(f"    OK uploaded")
                        fixed += 1
                        uploaded = True
                        break
                if not uploaded:
                    print(f"    FAIL all {len(candidates)} candidates rejected by Shopify")
                    failed += 1

            # Be polite to DDG — 10s between searches avoids rate limits
            time.sleep(10.0)

    print(f"\n{'-'*55}")
    print(f"Fixed: {fixed}   Failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start", type=int, default=0, help="Resume from product index N")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, start_at=args.start))
