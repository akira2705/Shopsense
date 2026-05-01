"""
Delete duplicate structured ShopSense catalog products.

Only products tagged shopsense-catalog-v2 are considered. The expected title set
comes from ensure_shopify_catalog.py; anything outside it, or duplicate copies of
an expected title, is removed.
"""

import asyncio
import os
from collections import defaultdict

import httpx
from dotenv import load_dotenv
from ensure_shopify_catalog import _build_products

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
        id
        title
        tags
      }
    }
  }
}
"""

DELETE_PRODUCT = """
mutation ProductDelete($input: ProductDeleteInput!) {
  productDelete(input: $input) {
    deletedProductId
    userErrors {
      field
      message
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


async def _structured_products(client: httpx.AsyncClient) -> list[dict]:
    result = []
    cursor = None
    while True:
        data = await _graphql(client, QUERY, {"cursor": cursor})
        products = data["data"]["products"]
        for edge in products["edges"]:
            node = edge["node"]
            if "shopsense-catalog-v2" in node["tags"]:
                result.append(node)
        if not products["pageInfo"]["hasNextPage"]:
            return result
        cursor = products["pageInfo"]["endCursor"]


async def main() -> int:
    expected_titles = {product["title"] for product in _build_products()}
    async with httpx.AsyncClient(timeout=30.0) as client:
        products = await _structured_products(client)

        by_title = defaultdict(list)
        for product in products:
            by_title[product["title"]].append(product)

        to_delete = []
        for product in products:
            if product["title"] not in expected_titles:
                to_delete.append(product)

        for title, copies in by_title.items():
            if title in expected_titles and len(copies) > 1:
                to_delete.extend(copies[1:])

        unique = {}
        for product in to_delete:
            unique[product["id"]] = product

        print(f"Structured products found: {len(products)}")
        print(f"Products to delete: {len(unique)}")

        for product in unique.values():
            data = await _graphql(client, DELETE_PRODUCT, {"input": {"id": product["id"]}})
            errors = data["data"]["productDelete"]["userErrors"]
            if errors:
                print(f"ERROR deleting {product['title']}: {errors}")
                return 1
            print(f"Deleted duplicate: {product['title']}")
            await asyncio.sleep(0.2)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
