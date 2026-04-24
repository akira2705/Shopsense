import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

_STORE_URL = os.getenv("SHOPIFY_STORE_URL", "")
_TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "")
_ENDPOINT = f"https://{_STORE_URL}/api/2024-01/graphql.json"
_HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Storefront-Access-Token": _TOKEN,
}

_PRODUCTS_QUERY = """
query SearchProducts($query: String!, $first: Int!) {
  products(query: $query, first: $first) {
    edges {
      node {
        id
        title
        description
        tags
        featuredImage {
          url
          altText
        }
        priceRange {
          minVariantPrice {
            amount
            currencyCode
          }
        }
        variants(first: 3) {
          edges {
            node {
              id
              title
              availableForSale
              price {
                amount
              }
            }
          }
        }
      }
    }
  }
}
"""

_CREATE_CART = """
mutation CreateCart($variantId: ID!, $quantity: Int!) {
  cartCreate(input: {
    lines: [{ quantity: $quantity, merchandiseId: $variantId }]
  }) {
    cart {
      checkoutUrl
    }
    userErrors {
      field
      message
    }
  }
}
"""


def _build_query_string(intent: dict) -> str:
    parts = []
    if intent.get("category"):
        parts.append(intent["category"])
    if intent.get("use_case"):
        parts.append(intent["use_case"])
    for constraint in (intent.get("constraints") or [])[:2]:
        parts.append(constraint)
    return " ".join(parts) if parts else "*"


def _parse_product(node: dict) -> dict:
    price_str = (
        node.get("priceRange", {})
        .get("minVariantPrice", {})
        .get("amount", "0")
    )
    try:
        price = float(price_str)
    except ValueError:
        price = 0.0

    variants = node.get("variants", {}).get("edges", [])
    variant_id = variants[0]["node"]["id"] if variants else None

    image = node.get("featuredImage")
    image_url = image["url"] if image else None

    return {
        "id": node["id"],
        "title": node["title"],
        "description": node.get("description", ""),
        "tags": node.get("tags", []),
        "price": price,
        "image_url": image_url,
        "variant_id": variant_id,
    }


async def search_products(intent: dict, limit: int = 15) -> list[dict]:
    query_string = _build_query_string(intent)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _ENDPOINT,
                headers=_HEADERS,
                json={
                    "query": _PRODUCTS_QUERY,
                    "variables": {"query": query_string, "first": limit},
                },
            )
            resp.raise_for_status()
            data = resp.json()

            edges = (
                data.get("data", {})
                .get("products", {})
                .get("edges", [])
            )
            products = [_parse_product(e["node"]) for e in edges]

            # Filter by budget
            budget_max = intent.get("budget_max")
            if budget_max:
                products = [p for p in products if p["price"] <= budget_max]

            return products

    except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as exc:
        print(f"[shopify_client] search_products error: {exc}")
        return []


async def search_products_broad(intent: dict) -> list[dict]:
    """Fallback: search without budget/tag constraints."""
    loose_intent = {"category": intent.get("category", "")}
    return await search_products(loose_intent, limit=10)


async def create_cart(variant_id: str, quantity: int = 1) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _ENDPOINT,
                headers=_HEADERS,
                json={
                    "query": _CREATE_CART,
                    "variables": {"variantId": variant_id, "quantity": quantity},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return (
                data.get("data", {})
                .get("cartCreate", {})
                .get("cart", {})
                .get("checkoutUrl")
            )
    except Exception as exc:
        print(f"[shopify_client] create_cart error: {exc}")
        return None
