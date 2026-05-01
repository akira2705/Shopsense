"""
Shopify Admin GraphQL client for ShopSense.

Uses the Admin API (not Storefront) so we can read all products and
use richer vendor/tag/type filters.

Required env vars:
  SHOPIFY_STORE_URL   = yourstore.myshopify.com
  SHOPIFY_ADMIN_TOKEN = shpat_xxxxxxxxxxxxxxxxxxxx

Aliases also supported:
  SHOPIFY_SHOP_DOMAIN         = yourstore.myshopify.com
  SHOPIFY_ADMIN_ACCESS_TOKEN  = shpat_xxxxxxxxxxxxxxxxxxxx

Output format matches browser_agent.py so the confidence engine,
ranker, and frontend need zero changes.
"""

import os
import re

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
    value = re.sub(r"^https?://", "", value)
    return value.split("/", 1)[0]


_STORE_URL = _normalize_shop_domain(
    _first_env("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN")
)
_ADMIN_TOKEN = _first_env("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_ADMIN_ACCESS_TOKEN")
_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2025-01").strip() or "2025-01"
_ENDPOINT    = f"https://{_STORE_URL}/admin/api/{_API_VERSION}/graphql.json"
_HEADERS     = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": _ADMIN_TOKEN,
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
        vendor
        productType
        onlineStoreUrl
        featuredImage {
          url
          altText
        }
        priceRangeV2 {
          minVariantPrice {
            amount
            currencyCode
          }
        }
        variants(first: 1) {
          edges {
            node {
              id
              price
            }
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


# ─── Query builder ─────────────────────────────────────────────────────────────

def _build_admin_query(intent: dict) -> str:
    """
    Build a Shopify Admin product search query string.

    Shopify Admin query syntax:
      - title:*keyword*     partial title match
      - tag:keyword         tag match
      - vendor:Brand        brand match
      - product_type:Type   product type match
      - status:ACTIVE       only live products

    We combine category, use-case, and brand terms into an OR expression.
    """
    parts: list[str] = ["status:ACTIVE"]
    or_terms: list[str] = []

    category = (intent.get("category") or "").strip()
    use_case = (intent.get("use_case") or "").strip()

    # Primary keyword: category words
    if category:
        for word in category.split():
            if len(word) >= 3:
                or_terms.append(f'title:*{word}*')
                or_terms.append(f'tag:{word}')

    # Use-case words expand the match surface
    if use_case:
        for word in use_case.split():
            if len(word) >= 3:
                or_terms.append(f'tag:{word}')

    # Brand constraint → vendor: filter (AND, not OR — it's a hard constraint)
    brand = _extract_brand(intent)
    if brand:
        parts.append(f'vendor:"{brand}"')

    if or_terms:
        parts.append(f'({" OR ".join(or_terms)})')

    return " ".join(parts) if parts else "status:ACTIVE"


def _extract_brand(intent: dict) -> str:
    """Pull brand from constraints list, e.g. 'brand: Nike' → 'Nike'."""
    for c in intent.get("constraints", []):
        if c.lower().startswith("brand:"):
            return c.split(":", 1)[1].strip()
    return ""


# ─── Product parser ─────────────────────────────────────────────────────────────

def _parse_metafields(mf_edges: list) -> dict:
    result: dict = {}
    for edge in mf_edges:
        node = edge.get("node", {})
        key = node.get("key", "")
        val = node.get("value", "")
        result[key] = val
    return result


def _parse_product(node: dict) -> dict:
    # Price: prefer first variant price (most accurate), fall back to range
    variants = node.get("variants", {}).get("edges", [])
    if variants:
        try:
            price = float(variants[0]["node"]["price"])
        except (KeyError, ValueError, TypeError):
            price = 0.0
        variant_id = variants[0]["node"].get("id")
    else:
        try:
            price = float(
                node.get("priceRangeV2", {})
                .get("minVariantPrice", {})
                .get("amount", "0")
            )
        except (ValueError, TypeError):
            price = 0.0
        variant_id = None

    # Image
    image = node.get("featuredImage")
    image_url = image["url"] if image else None

    # Metafields
    mf_edges = node.get("metafields", {}).get("edges", [])
    mf = _parse_metafields(mf_edges)

    # Rating / reviews from metafields
    try:
        rating = float(mf.get("rating", "") or 0) or None
    except (ValueError, TypeError):
        rating = None

    try:
        review_count = int(mf.get("review_count", "") or 0) or None
    except (ValueError, TypeError):
        review_count = None

    review_highlight = mf.get("review_highlight") or None
    category = mf.get("category") or None
    subcategory = mf.get("subcategory") or None
    model_type = mf.get("model_type") or None
    price_band = mf.get("price_band") or None

    # URL: use the online store URL if it exists, else build one from handle
    url = node.get("onlineStoreUrl")
    if not url and _STORE_URL:
        # Derive handle from product title (Shopify convention: lowercase, hyphens)
        slug = re.sub(r"[^a-z0-9]+", "-", node.get("title", "").lower()).strip("-")
        url = f"https://{_STORE_URL}/products/{slug}"

    # Tags: Shopify returns them as a flat list already
    tags = node.get("tags", [])

    # Extend tags with vendor and product_type for confidence engine matching
    vendor = (node.get("vendor") or "").strip()
    ptype  = (node.get("productType") or "").strip()
    if vendor and vendor.lower() not in [t.lower() for t in tags]:
        tags = [vendor] + tags
    if ptype and ptype.lower() not in [t.lower() for t in tags]:
        tags = tags + [ptype]

    return {
        "id":               node["id"],
        "title":            node["title"],
        "description":      node.get("description", ""),
        "tags":             tags,
        "price":            price,
        "image_url":        image_url,
        "variant_id":       variant_id,
        "rating":           rating,
        "review_count":     review_count,
        "review_highlight": review_highlight,
        "category":         category,
        "subcategory":      subcategory,
        "model_type":       model_type,
        "price_band":       price_band,
        "url":              url,
        "source":           "shopify",
    }


# ─── Public API ─────────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Return True when both env vars are present and non-empty."""
    return bool(_STORE_URL and _ADMIN_TOKEN)


async def list_products(limit: int = 25) -> list[dict]:
    """Return active Shopify products without applying an intent keyword filter."""
    return await _fetch_products("status:ACTIVE", limit)


async def search_products(intent: dict, limit: int = 20) -> list[dict]:
    """
    Search Shopify store products matching the intent.
    Returns [] on error or when not configured.
    """
    if not is_configured():
        return []

    query_string = _build_admin_query(intent)
    print(f"[shopify] query: {query_string!r}")

    products = await _fetch_products(query_string, limit)

    # Budget filter
    budget_max = intent.get("budget_max")
    if budget_max:
        products = [p for p in products if p["price"] <= budget_max]

    return products


async def search_products_broad(intent: dict) -> list[dict]:
    """Broad search: ignore budget, search only by category."""
    loose = {"category": intent.get("category", ""), "constraints": intent.get("constraints", [])}
    return await search_products(loose, limit=15)


async def _fetch_products(query_string: str, limit: int) -> list[dict]:
    if not is_configured():
        return []

    limit = max(1, min(int(limit), 100))
    print(f"[shopify] query: {query_string!r}")

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
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

            errors = data.get("errors")
            if errors:
                print(f"[shopify] GraphQL errors: {errors}")
                return []

            edges = (
                data.get("data", {})
                .get("products", {})
                .get("edges", [])
            )
            products = [_parse_product(e["node"]) for e in edges]
            print(f"[shopify] found {len(products)} products")
            return products

    except httpx.TimeoutException:
        print("[shopify] timeout")
        return []
    except httpx.HTTPStatusError as exc:
        print(f"[shopify] HTTP {exc.response.status_code}: {exc.response.text[:300]}")
        return []
    except Exception as exc:
        print(f"[shopify] error: {exc}")
        return []
