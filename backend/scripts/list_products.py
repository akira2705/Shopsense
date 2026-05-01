import asyncio, os, httpx
from dotenv import load_dotenv
load_dotenv()

def _norm(v):
    v = v.strip().rstrip("/").removeprefix("https://").removeprefix("http://")
    return v.split("/",1)[0]

STORE = _norm(os.getenv("SHOPIFY_STORE_URL",""))
TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN","")
BASE  = f"https://{STORE}/admin/api/2024-01"
H     = {"X-Shopify-Access-Token": TOKEN}

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        page_info = None
        all_products = []
        while True:
            url = f"{BASE}/products.json?limit=250&fields=id,title,vendor,product_type"
            if page_info:
                url += f"&page_info={page_info}"
            r = await c.get(url, headers=H)
            batch = r.json().get("products", [])
            all_products.extend(batch)
            link = r.headers.get("Link","")
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

        print(f"Total: {len(all_products)}\n")
        for p in sorted(all_products, key=lambda x: x["title"]):
            tid = p["id"]
            title = p["title"]
            vendor = p.get("vendor","")
            ptype = p.get("product_type","")
            print(f"{tid} | {vendor:20s} | {ptype:20s} | {title}")

asyncio.run(main())
