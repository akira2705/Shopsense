"""
remove_all_images.py — Strip ALL images from every Shopify product.
Usage: cd backend && py scripts/remove_all_images.py
"""
import asyncio, os, sys
import httpx
from dotenv import load_dotenv

load_dotenv()

def _first_env(*names):
    for n in names:
        v = os.getenv(n, "").strip()
        if v: return v
    return ""

def _norm(v):
    v = v.strip().rstrip("/").removeprefix("https://").removeprefix("http://")
    return v.split("/", 1)[0]

STORE   = _norm(_first_env("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN"))
TOKEN   = _first_env("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_ADMIN_ACCESS_TOKEN")
BASE    = f"https://{STORE}/admin/api/2024-01"
HEADERS = {"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN}

async def main():
    if not STORE or not TOKEN:
        print("ERROR: missing env vars"); sys.exit(1)

    async with httpx.AsyncClient(timeout=30) as client:
        removed = 0
        page_info = None

        while True:
            url = f"{BASE}/products.json?limit=250&fields=id,title,images"
            if page_info:
                url += f"&page_info={page_info}"
            r = await client.get(url, headers=HEADERS)
            r.raise_for_status()
            products = r.json().get("products", [])
            if not products:
                break

            for p in products:
                images = p.get("images", [])
                if not images:
                    continue
                for img in images:
                    dr = await client.delete(
                        f"{BASE}/products/{p['id']}/images/{img['id']}.json",
                        headers=HEADERS
                    )
                    if dr.status_code == 200:
                        removed += 1
                    await asyncio.sleep(0.25)
                print(f"  cleared {len(images)} image(s): {p['title']}")

            link = r.headers.get("Link", "")
            if 'rel="next"' in link:
                for part in link.split(","):
                    if 'rel="next"' in part:
                        for param in part.split(";")[0].strip().strip("<>").split("&"):
                            if param.startswith("page_info="):
                                page_info = param.split("=",1)[1]
                                break
                        break
            else:
                break

        print(f"\nDone. Removed {removed} images total.")

if __name__ == "__main__":
    asyncio.run(main())
