"""
remove_bad_images.py — Delete images from products that got the wrong image
(specifically the aeplcdn.com used-car photo uploaded due to 'skincare' bug).

Usage:
    cd backend
    py -u scripts/remove_bad_images.py
"""
import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def _norm(v):
    v = v.strip().rstrip("/").removeprefix("https://").removeprefix("http://")
    return v.split("/", 1)[0]

def _first_env(*names):
    for n in names:
        v = os.getenv(n, "").strip()
        if v: return v
    return ""

STORE        = _norm(_first_env("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN"))
TOKEN        = _first_env("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_ADMIN_ACCESS_TOKEN")
BASE         = f"https://{STORE}/admin/api/2024-01"
SHOP_HEADERS = {"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN}

# The bad image filename (Shopify re-hosts it but keeps the original name)
BAD_SRC = "oz6ojtbnxuiz"


async def get_all_products(client):
    products = []
    page_info = None
    while True:
        url = f"{BASE}/products.json?limit=250&fields=id,title,product_type,images"
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


async def main():
    print(f"Store: {STORE}")
    print("Fetching products to find bad images...")

    async with httpx.AsyncClient(timeout=30) as client:
        products = await get_all_products(client)

    removed = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for p in products:
            for img in p.get("images", []):
                src = img.get("src", "")
                if BAD_SRC in src:
                    img_id = img["id"]
                    pid    = p["id"]
                    title  = p["title"]
                    print(f"Removing bad image from: {title}")
                    r = await client.delete(
                        f"{BASE}/products/{pid}/images/{img_id}.json",
                        headers=SHOP_HEADERS,
                    )
                    if r.status_code == 200:
                        print(f"  OK deleted")
                        removed += 1
                    else:
                        print(f"  FAIL {r.status_code}")
                    await asyncio.sleep(0.5)

    print(f"\nDone. Removed {removed} bad images.")

asyncio.run(main())
