"""
Read existing products from the configured Shopify dev store.

Usage:
    cd backend
    python scripts/list_shopify_products.py
    python scripts/list_shopify_products.py --query "running shoes" --limit 10
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent import shopify_client


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List Shopify products for ShopSense.")
    parser.add_argument("--query", default="", help="Optional product/category search text.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum products to read.")
    return parser


async def main() -> int:
    args = _build_parser().parse_args()

    if not shopify_client.is_configured():
        print(
            "ERROR: Set SHOPIFY_STORE_URL and SHOPIFY_ADMIN_TOKEN in backend/.env "
            "or use SHOPIFY_SHOP_DOMAIN and SHOPIFY_ADMIN_ACCESS_TOKEN."
        )
        return 1

    if args.query:
        products = await shopify_client.search_products(
            {"category": args.query, "constraints": []},
            limit=args.limit,
        )
    else:
        products = await shopify_client.list_products(limit=args.limit)

    print(json.dumps(products, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
