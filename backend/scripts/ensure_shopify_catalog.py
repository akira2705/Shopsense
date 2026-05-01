"""
Create a broad ShopSense demo catalog in Shopify.

Each category/subcategory/model group gets exactly six synthetic products,
ordered from cheap to expensive. The script is idempotent by title, so rerunning
it skips products already present in the store.
"""

import asyncio
import os
import sys
from pathlib import Path

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

CREATE_PRODUCT = """
mutation ProductCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
      variants(first: 1) {
        edges {
          node {
            id
          }
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

UPDATE_VARIANT_PRICE = """
mutation ProductVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      price
    }
    userErrors {
      field
      message
    }
  }
}
"""

SET_METAFIELDS = """
mutation SetMetafields($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    userErrors {
      field
      message
    }
  }
}
"""

EXISTING_PRODUCTS = """
query ExistingProducts($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        title
      }
    }
  }
}
"""

TIERS = [
    ("Value", "cheap", 4.1),
    ("Everyday", "budget", 4.2),
    ("Plus", "mid-range", 4.3),
    ("Pro", "upper-mid", 4.5),
    ("Elite", "premium", 4.6),
    ("Ultra", "luxury", 4.7),
]

CATALOG = {
    "Covers & Cases": {
        "Phone Cases": {
            "model_type": "protective cover",
            "base_prices": [199, 399, 699, 999, 1499, 2499],
            "items": [
                ("CaseMate", "Clear Shield Case"),
                ("DailyObjects", "Silicone Grip Case"),
                ("Spigen", "Rugged Armor Case"),
                ("Ringke", "Fusion MagSafe Case"),
                ("OtterBox", "Defender Case"),
                ("Mous", "Limitless Aramid Case"),
            ],
        },
        "Laptop Sleeves": {
            "model_type": "sleeve",
            "base_prices": [349, 599, 899, 1299, 1999, 3299],
            "items": [
                ("AmazonBasics", "Neoprene Sleeve"),
                ("Tukzer", "Canvas Sleeve"),
                ("DailyObjects", "Slim Sleeve"),
                ("Lenovo", "Urban Sleeve"),
                ("tomtoc", "360 Protective Sleeve"),
                ("Native Union", "Stow Lite Sleeve"),
            ],
        },
        "Tablet Covers": {
            "model_type": "folio case",
            "base_prices": [299, 549, 899, 1399, 2199, 3499],
            "items": [
                ("ProElite", "Trifold Stand Cover"),
                ("ESR", "Rebound Folio"),
                ("Spigen", "Urban Fit Cover"),
                ("Logitech", "Slim Folio"),
                ("Apple", "Smart Folio"),
                ("ZAGG", "Rugged Book Cover"),
            ],
        },
    },
    "Phones": {
        "Budget Smartphones": {
            "model_type": "android phone",
            "base_prices": [7999, 9999, 11999, 13999, 15999, 17999],
            "items": [
                ("itel", "A70"),
                ("Redmi", "13C"),
                ("Realme", "Narzo N63"),
                ("Samsung", "Galaxy M14"),
                ("Moto", "G34 5G"),
                ("Poco", "M6 Pro 5G"),
            ],
        },
        "Midrange Smartphones": {
            "model_type": "5g phone",
            "base_prices": [18999, 21999, 24999, 29999, 34999, 39999],
            "items": [
                ("iQOO", "Z9 5G"),
                ("OnePlus", "Nord CE4"),
                ("Nothing", "Phone 2a"),
                ("Redmi", "Note 13 Pro+"),
                ("Samsung", "Galaxy A55"),
                ("Vivo", "V30 Pro"),
            ],
        },
        "Flagship Smartphones": {
            "model_type": "flagship phone",
            "base_prices": [49999, 59999, 69999, 79999, 99999, 129999],
            "items": [
                ("Google", "Pixel 8"),
                ("OnePlus", "12"),
                ("Samsung", "Galaxy S24"),
                ("iQOO", "12 Legend"),
                ("Apple", "iPhone 15 Pro"),
                ("Samsung", "Galaxy S24 Ultra"),
            ],
        },
    },
    "Electronics": {
        "Smartwatches": {
            "model_type": "wearable",
            "base_prices": [1499, 2499, 4999, 9999, 24999, 45999],
            "items": [
                ("Noise", "ColorFit Pulse"),
                ("boAt", "Wave Sigma"),
                ("Amazfit", "Bip 5"),
                ("OnePlus", "Watch 2R"),
                ("Samsung", "Galaxy Watch6"),
                ("Apple", "Watch Series 9"),
            ],
        },
        "Bluetooth Speakers": {
            "model_type": "speaker",
            "base_prices": [799, 1499, 2999, 5999, 11999, 24999],
            "items": [
                ("Portronics", "SoundDrum Mini"),
                ("boAt", "Stone 352"),
                ("JBL", "Go 4"),
                ("Sony", "XB100"),
                ("Marshall", "Willen"),
                ("Bose", "SoundLink Flex"),
            ],
        },
        "Power Banks": {
            "model_type": "charger",
            "base_prices": [699, 999, 1499, 2499, 3999, 6999],
            "items": [
                ("Ambrane", "Capsule 10K"),
                ("Mi", "Power Bank 3i"),
                ("URBN", "Nano 10K"),
                ("Anker", "PowerCore 20K"),
                ("Stuffcool", "Major Max"),
                ("Anker", "Prime 27K"),
            ],
        },
    },
    "Home Appliances": {
        "Air Fryers": {
            "model_type": "kitchen appliance",
            "base_prices": [2999, 4499, 6499, 8999, 12999, 18999],
            "items": [
                ("Pigeon", "Healthifry 4L"),
                ("KENT", "Classic Hot Air Fryer"),
                ("Philips", "Essential Air Fryer"),
                ("Havells", "Prolife Grande"),
                ("Instant", "Vortex Plus"),
                ("Ninja", "Foodi Dual Zone"),
            ],
        },
        "Vacuum Cleaners": {
            "model_type": "cleaning appliance",
            "base_prices": [2499, 4999, 7999, 14999, 29999, 54999],
            "items": [
                ("Eureka Forbes", "Quick Clean DX"),
                ("Karcher", "WD 1 Classic"),
                ("Philips", "PowerPro Compact"),
                ("AGARO", "Regal Plus"),
                ("Dyson", "V8 Absolute"),
                ("Dyson", "V12 Detect Slim"),
            ],
        },
        "Mixer Grinders": {
            "model_type": "kitchen appliance",
            "base_prices": [1299, 2199, 3499, 4999, 7999, 12999],
            "items": [
                ("Bajaj", "Rex 500W"),
                ("Prestige", "Iris Plus"),
                ("Butterfly", "Jet Elite"),
                ("Philips", "HL7756"),
                ("Bosch", "TrueMixx Pro"),
                ("Sujata", "Dynamix DX"),
            ],
        },
    },
    "Cars": {
        "Hatchbacks": {
            "model_type": "car",
            "base_prices": [325000, 450000, 575000, 699000, 825000, 990000],
            "items": [
                ("Maruti Suzuki", "Alto K10"),
                ("Renault", "Kwid"),
                ("Maruti Suzuki", "Celerio"),
                ("Hyundai", "Grand i10 Nios"),
                ("Tata", "Altroz"),
                ("Maruti Suzuki", "Baleno"),
            ],
        },
        "SUVs": {
            "model_type": "car",
            "base_prices": [699000, 899000, 1199000, 1599000, 2299000, 3499000],
            "items": [
                ("Tata", "Punch"),
                ("Hyundai", "Venue"),
                ("Maruti Suzuki", "Brezza"),
                ("Kia", "Seltos"),
                ("Mahindra", "XUV700"),
                ("Toyota", "Fortuner"),
            ],
        },
        "Electric Cars": {
            "model_type": "ev car",
            "base_prices": [799000, 1099000, 1399000, 1699000, 2499000, 4999000],
            "items": [
                ("MG", "Comet EV"),
                ("Tata", "Tiago EV"),
                ("Tata", "Punch EV"),
                ("Mahindra", "XUV400"),
                ("BYD", "Atto 3"),
                ("Hyundai", "Ioniq 5"),
            ],
        },
    },
    "Toys": {
        "STEM Toys": {
            "model_type": "educational toy",
            "base_prices": [299, 599, 999, 1799, 2999, 4999],
            "items": [
                ("Smartivity", "Hydraulic Crane Kit"),
                ("Einstein Box", "Science Explorer"),
                ("PlayShifu", "Tacto Coding"),
                ("LEGO", "Education BricQ Set"),
                ("Sphero", "Mini Coding Robot"),
                ("Makeblock", "mBot Robot Kit"),
            ],
        },
        "Action Figures": {
            "model_type": "collectible toy",
            "base_prices": [199, 499, 899, 1499, 2499, 3999],
            "items": [
                ("Funskool", "Hero Mini Figure"),
                ("Hasbro", "Marvel Titan Hero"),
                ("Mattel", "Jurassic World Dino"),
                ("Bandai", "Anime Heroes Figure"),
                ("McFarlane", "DC Multiverse Figure"),
                ("Hot Toys", "Collector Figure"),
            ],
        },
        "Outdoor Toys": {
            "model_type": "active toy",
            "base_prices": [349, 699, 1299, 2499, 3999, 6999],
            "items": [
                ("Nerf", "Alpha Strike Blaster"),
                ("Toyshine", "Bubble Machine"),
                ("R for Rabbit", "Scooter Junior"),
                ("Decathlon", "Kids Trampoline"),
                ("VTech", "KidiZoom Camera"),
                ("Segway", "Ninebot Kids Scooter"),
            ],
        },
    },
    "Board Games": {
        "Family Games": {
            "model_type": "board game",
            "base_prices": [199, 399, 699, 999, 1499, 2499],
            "items": [
                ("Funskool", "Ludo Classic"),
                ("Hasbro", "Monopoly Junior"),
                ("Mattel", "UNO Party"),
                ("Spin Master", "Hedbanz"),
                ("Hasbro", "The Game of Life"),
                ("Days of Wonder", "Ticket to Ride"),
            ],
        },
        "Strategy Games": {
            "model_type": "strategy board game",
            "base_prices": [499, 999, 1799, 2999, 4499, 6999],
            "items": [
                ("Stonemaier", "Rolling Realms"),
                ("Kosmos", "Catan Junior"),
                ("Asmodee", "Splendor"),
                ("Days of Wonder", "Small World"),
                ("Stonemaier", "Wingspan"),
                ("Cephalofair", "Gloomhaven Jaws"),
            ],
        },
        "Party Games": {
            "model_type": "party game",
            "base_prices": [299, 599, 999, 1499, 2299, 3499],
            "items": [
                ("Taco Cat Goat", "Card Game"),
                ("Exploding Kittens", "Original Edition"),
                ("Hasbro", "Taboo"),
                ("Big Potato", "Herd Mentality"),
                ("Repos", "Just One"),
                ("Codenames", "Pictures XXL"),
            ],
        },
    },
    "Fashion": {
        "Running Shoes": {
            "model_type": "footwear",
            "base_prices": [1499, 2499, 3999, 6999, 9999, 14999],
            "items": [
                ("Campus", "Oxyfit Running Shoe"),
                ("Sparx", "Mesh Runner"),
                ("Puma", "Velocity Runner"),
                ("Nike", "Downshifter"),
                ("Adidas", "Ultraboost Light"),
                ("ASICS", "Gel Nimbus"),
            ],
        },
        "Backpacks": {
            "model_type": "bag",
            "base_prices": [499, 999, 1799, 2999, 4999, 8999],
            "items": [
                ("Skybags", "Campus Daypack"),
                ("Wildcraft", "Wiki Backpack"),
                ("American Tourister", "Urban Pack"),
                ("F Gear", "Luxur Backpack"),
                ("Samsonite", "Ikonn Laptop Backpack"),
                ("Tumi", "Alpha Bravo Backpack"),
            ],
        },
        "Watches": {
            "model_type": "fashion accessory",
            "base_prices": [699, 1499, 2999, 5999, 12999, 29999],
            "items": [
                ("Sonata", "Essentials Analog"),
                ("Fastrack", "Trendies Watch"),
                ("Casio", "Enticer Analog"),
                ("Titan", "Neo Splash"),
                ("Seiko", "DressKX Automatic"),
                ("Tissot", "PRX Quartz"),
            ],
        },
    },
}


def _slug(value: str) -> str:
    return value.lower().replace("&", "and").replace(" ", "-")


def _build_products() -> list[dict]:
    products = []
    for category, subcategories in CATALOG.items():
        for subcategory, spec in subcategories.items():
            for index, ((vendor, name), price) in enumerate(zip(spec["items"], spec["base_prices"])):
                tier, price_band, rating = TIERS[index]
                title = f"{vendor} {name} {tier}"
                products.append({
                    "title": title,
                    "vendor": vendor,
                    "product_type": category,
                    "category": category,
                    "subcategory": subcategory,
                    "model_type": spec["model_type"],
                    "price_band": price_band,
                    "price": price,
                    "rating": rating,
                    "review_count": 400 + (index + 1) * 731,
                    "review_highlight": (
                        f"{tier} pick for {subcategory.lower()} shoppers who want "
                        f"{price_band.replace('-', ' ')} value."
                    ),
                    "tags": [
                        "shopsense-catalog-v2",
                        _slug(category),
                        _slug(subcategory),
                        _slug(spec["model_type"]),
                        price_band,
                        tier.lower(),
                    ],
                    "description": (
                        f"Synthetic ShopSense demo product in {category} > {subcategory}. "
                        f"Model/type: {spec['model_type']}. It is positioned as the "
                        f"{price_band.replace('-', ' ')} option in a six-product price ladder."
                    ),
                })
    return products


async def _graphql(client: httpx.AsyncClient, query: str, variables: dict | None = None) -> dict:
    resp = await client.post(
        ENDPOINT,
        headers=HEADERS,
        json={"query": query, "variables": variables or {}},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data


async def _existing_titles(client: httpx.AsyncClient) -> set[str]:
    titles: set[str] = set()
    cursor = None
    while True:
        data = await _graphql(client, EXISTING_PRODUCTS, {"cursor": cursor})
        products = data["data"]["products"]
        titles.update(edge["node"]["title"] for edge in products["edges"])
        if not products["pageInfo"]["hasNextPage"]:
            return titles
        cursor = products["pageInfo"]["endCursor"]


async def _create_product(client: httpx.AsyncClient, product: dict) -> str | None:
    input_data = {
        "title": product["title"],
        "vendor": product["vendor"],
        "productType": product["product_type"],
        "tags": product["tags"],
        "descriptionHtml": product["description"],
        "status": "ACTIVE",
    }
    data = await _graphql(client, CREATE_PRODUCT, {"input": input_data})
    result = data["data"]["productCreate"]
    if result["userErrors"]:
        print(f"  ERROR {product['title']}: {result['userErrors']}")
        return None

    created_product = result["product"]
    variant_edges = created_product.get("variants", {}).get("edges", [])
    if variant_edges:
        variant_id = variant_edges[0]["node"]["id"]
        price_result = await _graphql(
            client,
            UPDATE_VARIANT_PRICE,
            {
                "productId": created_product["id"],
                "variants": [{"id": variant_id, "price": str(product["price"])}],
            },
        )
        errors = price_result["data"]["productVariantsBulkUpdate"]["userErrors"]
        if errors:
            print(f"  WARN price for {product['title']}: {errors}")

    return created_product["id"]


async def _set_metafields(client: httpx.AsyncClient, owner_id: str, product: dict) -> None:
    metafields = [
        ("category", product["category"], "single_line_text_field"),
        ("subcategory", product["subcategory"], "single_line_text_field"),
        ("model_type", product["model_type"], "single_line_text_field"),
        ("price_band", product["price_band"], "single_line_text_field"),
        ("rating", str(product["rating"]), "number_decimal"),
        ("review_count", str(product["review_count"]), "number_integer"),
        ("review_highlight", product["review_highlight"], "single_line_text_field"),
    ]
    payload = [
        {
            "ownerId": owner_id,
            "namespace": "shopsense",
            "key": key,
            "value": value,
            "type": field_type,
        }
        for key, value, field_type in metafields
    ]
    data = await _graphql(client, SET_METAFIELDS, {"metafields": payload})
    errors = data["data"]["metafieldsSet"]["userErrors"]
    if errors:
        print(f"  WARN metafields for {product['title']}: {errors}")


async def main() -> int:
    if not STORE_URL or not ADMIN_TOKEN:
        print("ERROR: Set SHOPIFY_STORE_URL and SHOPIFY_ADMIN_TOKEN in backend/.env")
        return 1

    products = _build_products()
    print(f"Ensuring {len(products)} structured products in {STORE_URL}...")

    created = 0
    skipped = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        existing = await _existing_titles(client)
        print(f"Existing products before: {len(existing)}")

        for index, product in enumerate(products, 1):
            if product["title"] in existing:
                skipped += 1
                continue

            product_id = await _create_product(client, product)
            if product_id:
                await _set_metafields(client, product_id, product)
                created += 1
                print(f"[{index:03d}/{len(products)}] created {product['title']}")
            else:
                failed += 1

            await asyncio.sleep(0.35)

    print(f"Created: {created}  Skipped: {skipped}  Failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
