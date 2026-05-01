"""
Verify the structured ShopSense Shopify catalog.
"""

import asyncio
import os
from collections import defaultdict

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
        priceRangeV2 {
          minVariantPrice {
            amount
          }
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


async def _graphql(client: httpx.AsyncClient, query: str, variables: dict) -> dict:
    resp = await client.post(ENDPOINT, headers=HEADERS, json={"query": query, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data


async def _products() -> list[dict]:
    result = []
    cursor = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            data = await _graphql(client, QUERY, {"cursor": cursor})
            products = data["data"]["products"]
            for edge in products["edges"]:
                node = edge["node"]
                metafields = {
                    item["node"]["key"]: item["node"]["value"]
                    for item in node["metafields"]["edges"]
                }
                result.append({
                    "title": node["title"],
                    "tags": node["tags"],
                    "category": metafields.get("category"),
                    "subcategory": metafields.get("subcategory"),
                    "model_type": metafields.get("model_type"),
                    "price_band": metafields.get("price_band"),
                    "price": float(node["priceRangeV2"]["minVariantPrice"]["amount"]),
                })
            if not products["pageInfo"]["hasNextPage"]:
                return result
            cursor = products["pageInfo"]["endCursor"]


async def main() -> int:
    products = await _products()
    structured = [p for p in products if "shopsense-catalog-v2" in p["tags"]]
    counts = defaultdict(list)

    for product in structured:
        key = (product["category"], product["subcategory"], product["model_type"])
        counts[key].append(product)

    print(f"Total active products: {len(products)}")
    print(f"Structured ShopSense products: {len(structured)}")

    bad = []
    for key in sorted(counts):
        items = sorted(counts[key], key=lambda item: item["price"])
        prices = ", ".join(str(int(item["price"])) for item in items)
        print(f"{key[0]} > {key[1]} > {key[2]}: {len(items)} products [{prices}]")
        if len(items) != 6:
            bad.append((key, items))

    if bad:
        print("\nGroups needing attention:")
        for key, items in bad:
            titles = "; ".join(item["title"] for item in sorted(items, key=lambda item: item["price"]))
            print(f"- {key}: {len(items)} products: {titles}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
