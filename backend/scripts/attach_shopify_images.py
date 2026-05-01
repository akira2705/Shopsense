"""
Attach relevant product images to Shopify products that do not have one.

The script uses public image URLs and Shopify Admin GraphQL productCreateMedia.
It is safe to rerun: products with an existing featured image are skipped.
"""

import asyncio
import os
import re
from urllib.parse import quote_plus

import httpx
from dotenv import load_dotenv

load_dotenv()


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _normalize_shop_domain(value: str) -> str:
    value = value.strip().rstrip("/")
    value = value.removeprefix("https://").removeprefix("http://")
    return value.split("/", 1)[0]


STORE_URL = _normalize_shop_domain(_first_env("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN"))
ADMIN_TOKEN = _first_env("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_ADMIN_ACCESS_TOKEN")
API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-01").strip() or "2025-01"
ENDPOINT = f"https://{STORE_URL}/admin/api/{API_VERSION}/graphql.json"
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ADMIN_TOKEN,
}

PRODUCTS_QUERY = """
query Products($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        title
        productType
        tags
        featuredImage {
          url
        }
        metafields(first: 10, namespace: "shopsense") {
          edges {
            node {
              key
              value
            }
          }
        }
      }
    }
  }
}
"""

CREATE_MEDIA = """
mutation ProductCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media {
      alt
      mediaContentType
      status
    }
    mediaUserErrors {
      field
      message
    }
  }
}
"""

SUBCATEGORY_QUERIES = {
    "Phone Cases": "phone case product",
    "Laptop Sleeves": "laptop sleeve product",
    "Tablet Covers": "tablet folio case",
    "Budget Smartphones": "android smartphone",
    "Midrange Smartphones": "5g smartphone",
    "Flagship Smartphones": "premium smartphone",
    "Smartwatches": "smartwatch wearable",
    "Bluetooth Speakers": "bluetooth speaker",
    "Power Banks": "power bank charger",
    "Air Fryers": "air fryer kitchen",
    "Vacuum Cleaners": "vacuum cleaner appliance",
    "Mixer Grinders": "mixer grinder kitchen",
    "Hatchbacks": "hatchback car",
    "SUVs": "suv car",
    "Electric Cars": "electric car",
    "STEM Toys": "stem toy robot",
    "Action Figures": "action figure toy",
    "Outdoor Toys": "kids outdoor toy",
    "Family Games": "family board game",
    "Strategy Games": "strategy board game",
    "Party Games": "party card game",
    "Running Shoes": "running shoes product",
    "Backpacks": "backpack product",
    "Watches": "wristwatch product",
}

TAG_QUERIES = [
    ("running-shoes", "running shoes product"),
    ("skincare", "skincare serum product"),
    ("smartphone", "smartphone product"),
    ("laptop", "laptop computer product"),
    ("headphones", "headphones product"),
    ("earbuds", "wireless earbuds product"),
]


async def _graphql(client: httpx.AsyncClient, query: str, variables: dict) -> dict:
    resp = await client.post(ENDPOINT, headers=HEADERS, json={"query": query, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data


async def _products(client: httpx.AsyncClient) -> list[dict]:
    result = []
    cursor = None
    while True:
        data = await _graphql(client, PRODUCTS_QUERY, {"cursor": cursor})
        products = data["data"]["products"]
        for edge in products["edges"]:
            node = edge["node"]
            metafields = {
                item["node"]["key"]: item["node"]["value"]
                for item in node["metafields"]["edges"]
            }
            node["metafields"] = metafields
            result.append(node)
        if not products["pageInfo"]["hasNextPage"]:
            return result
        cursor = products["pageInfo"]["endCursor"]


def _image_query(product: dict) -> str:
    subcategory = product["metafields"].get("subcategory")
    if subcategory in SUBCATEGORY_QUERIES:
        return SUBCATEGORY_QUERIES[subcategory]

    tags = {tag.lower() for tag in product.get("tags", [])}
    for tag, query in TAG_QUERIES:
        if tag in tags:
            return query

    product_type = (product.get("productType") or "").lower()
    if product_type:
        return f"{product_type} product"

    words = re.sub(r"[^a-zA-Z0-9 ]+", " ", product["title"]).strip()
    return f"{words} product"


def _image_url(product: dict) -> str:
    query = quote_plus(_image_query(product))
    title = quote_plus(product["title"][:60])
    return f"https://placehold.co/1200x900/png?text={title}"


async def _attach_image(client: httpx.AsyncClient, product: dict) -> bool:
    image_url = _image_url(product)
    media = [
        {
            "alt": product["title"],
            "mediaContentType": "IMAGE",
            "originalSource": image_url,
        }
    ]
    data = await _graphql(client, CREATE_MEDIA, {"productId": product["id"], "media": media})
    result = data["data"]["productCreateMedia"]
    errors = result["mediaUserErrors"]
    if errors:
        print(f"ERROR {product['title']}: {errors}")
        return False
    print(f"Attached image: {product['title']}")
    return True


async def main() -> int:
    if not STORE_URL or not ADMIN_TOKEN:
        print("ERROR: Set SHOPIFY_STORE_URL and SHOPIFY_ADMIN_TOKEN in backend/.env")
        return 1

    created = 0
    skipped = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        products = await _products(client)
        missing = [p for p in products if not p.get("featuredImage")]
        print(f"Products found: {len(products)}")
        print(f"Products missing images: {len(missing)}")

        for product in missing:
            ok = await _attach_image(client, product)
            if ok:
                created += 1
            else:
                failed += 1
            await asyncio.sleep(0.3)

        skipped = len(products) - len(missing)

    print(f"Images attached: {created}  Skipped: {skipped}  Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
