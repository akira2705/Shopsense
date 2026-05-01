"""
Verify Shopify product image coverage.
"""

import asyncio
import os

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

QUERY = """
query Products($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        title
        tags
        featuredImage {
          url
        }
      }
    }
  }
}
"""


async def _graphql(client: httpx.AsyncClient, variables: dict) -> dict:
    resp = await client.post(ENDPOINT, headers=HEADERS, json={"query": QUERY, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data


async def main() -> int:
    total = 0
    with_images = 0
    structured_total = 0
    structured_with_images = 0
    missing = []
    cursor = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            data = await _graphql(client, {"cursor": cursor})
            products = data["data"]["products"]
            for edge in products["edges"]:
                product = edge["node"]
                total += 1
                has_image = bool(product.get("featuredImage"))
                is_structured = "shopsense-catalog-v2" in product["tags"]
                if has_image:
                    with_images += 1
                else:
                    missing.append(product["title"])
                if is_structured:
                    structured_total += 1
                    if has_image:
                        structured_with_images += 1

            if not products["pageInfo"]["hasNextPage"]:
                break
            cursor = products["pageInfo"]["endCursor"]

    print(f"Total products: {total}")
    print(f"Products with images: {with_images}")
    print(f"Structured products with images: {structured_with_images}/{structured_total}")
    if missing:
        print("Missing images:")
        for title in missing:
            print(f"- {title}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
