"""
fix_product_names.py — Rename Shopify products to accurate real-world model names.
Also deletes true duplicates.

Usage:
    cd backend
    py scripts/fix_product_names.py --dry-run   # preview changes
    py scripts/fix_product_names.py              # apply
"""
import argparse
import asyncio
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

def _norm(v):
    v = v.strip().rstrip("/").removeprefix("https://").removeprefix("http://")
    return v.split("/", 1)[0]

def _first_env(*names):
    for n in names:
        v = os.getenv(n, "").strip()
        if v: return v
    return ""

STORE   = _norm(_first_env("SHOPIFY_STORE_URL", "SHOPIFY_SHOP_DOMAIN"))
TOKEN   = _first_env("SHOPIFY_ADMIN_TOKEN", "SHOPIFY_ADMIN_ACCESS_TOKEN")
BASE    = f"https://{STORE}/admin/api/2024-01"
H       = {"Content-Type": "application/json", "X-Shopify-Access-Token": TOKEN}

# ─── Rename map: current title → correct real-world name ────────────────────────
# Rule: strip tier suffix (Value/Plus/Pro/Elite/Ultra/Everyday/Legend)
# unless it's genuinely part of the model name.

RENAMES = {
    # ── PHONES & ELECTRONICS ────────────────────────────────────────────────────
    "Apple iPhone 15 Pro Elite":            "Apple iPhone 15 Pro",
    "Apple Watch Series 9 Ultra":           "Apple Watch Series 9",
    "Apple Smart Folio Elite":              "Apple Smart Folio",
    "Amazfit Bip 5 Plus":                   "Amazfit Bip 5",
    "Anker PowerCore 20K Pro":              "Anker PowerCore 20000",
    "Anker Prime 27K Ultra":                "Anker Prime 27600",
    "boAt Stone 352 Everyday":              "boAt Stone 352",
    "boAt Wave Sigma Everyday":             "boAt Wave Sigma",
    "Bose SoundLink Flex Ultra":            "Bose SoundLink Flex",
    "Google Pixel 8 Value":                 "Google Pixel 8",
    "iQOO 12 Legend Pro":                   "iQOO 12",
    "iQOO Z9 5G Value":                     "iQOO Z9 5G",
    "itel A70 Value":                       "itel A70",
    "JBL Go 4 Plus":                        "JBL Go 4",
    "Marshall Willen Elite":                "Marshall Willen",
    "Mi Power Bank 3i Everyday":            "Mi Power Bank 3i",
    "Moto G34 5G Elite":                    "Moto G34 5G",
    "Noise ColorFit Pulse Value":           "Noise ColorFit Pulse",
    "Nothing Phone 2a Plus":                "Nothing Phone 2a",
    "OnePlus Watch 2R Pro":                 "OnePlus Watch 2R",
    "Poco M6 Pro 5G Ultra":                 "Poco M6 Pro 5G",
    "Portronics SoundDrum Mini Value":      "Portronics SoundDrum Mini",
    "Realme Narzo N63 Plus":                "Realme Narzo N55",
    "Redmi 13C Everyday":                   "Redmi 13C",
    "Redmi Note 13 Pro+ Pro":               "Redmi Note 13 Pro+",
    "Samsung Galaxy A55 Elite":             "Samsung Galaxy A55 5G",    # duplicate — rename to match
    "Samsung Galaxy M14 Pro":               "Samsung Galaxy M14 5G",
    "Samsung Galaxy S24 Plus":              "Samsung Galaxy S24+",
    "Samsung Galaxy S24 Ultra Ultra":       "Samsung Galaxy S24 Ultra",
    "Samsung Galaxy Watch6 Elite":          "Samsung Galaxy Watch 6",
    "Sony XB100 Pro":                       "Sony SRS-XB100",
    "Stuffcool Major Max Elite":            "Stuffcool Major Max",
    "URBN Nano 10K Plus":                   "URBN Nano 10000mAh",
    "Vivo V30 Pro Ultra":                   "Vivo V30 Pro",

    # ── CARS ────────────────────────────────────────────────────────────────────
    "BYD Atto 3 Elite":                     "BYD Atto 3",
    "Hyundai Grand i10 Nios Pro":           "Hyundai Grand i10 Nios",
    "Hyundai Ioniq 5 Ultra":                "Hyundai Ioniq 5",
    "Hyundai Venue Everyday":               "Hyundai Venue",
    "Kia Seltos Pro":                       "Kia Seltos",
    "MG Comet EV Value":                    "MG Comet EV",
    "Mahindra XUV400 Pro":                  "Mahindra XUV400",
    "Mahindra XUV700 Elite":                "Mahindra XUV700",
    "Maruti Suzuki Alto K10 Value":         "Maruti Suzuki Alto K10",
    "Maruti Suzuki Baleno Ultra":           "Maruti Suzuki Baleno",
    "Maruti Suzuki Brezza Plus":            "Maruti Suzuki Brezza",
    "Maruti Suzuki Celerio Plus":           "Maruti Suzuki Celerio",
    "Renault Kwid Everyday":               "Renault Kwid",
    "Tata Altroz Elite":                    "Tata Altroz",
    "Tata Punch EV Plus":                   "Tata Punch EV",
    "Tata Punch Value":                     "Tata Punch",
    "Tata Tiago EV Everyday":               "Tata Tiago EV",
    "Toyota Fortuner Ultra":                "Toyota Fortuner",

    # ── RUNNING SHOES & FASHION ─────────────────────────────────────────────────
    "Adidas Ultraboost Light Elite":        "Adidas Ultraboost Light",
    "ASICS Gel Nimbus Ultra":               "ASICS Gel Nimbus 25",
    "Campus Oxyfit Running Shoe Value":     "Campus Oxyfit",
    "Casio Enticer Analog Plus":            "Casio Enticer",
    "F Gear Luxur Backpack Pro":            "F Gear Luxur",
    "Fastrack Trendies Watch Everyday":     "Fastrack Trendies",
    "Nike Downshifter Pro":                 "Nike Downshifter 13",
    "Puma Velocity Runner Plus":            "Puma Velocity Nitro 3",
    "Samsonite Ikonn Laptop Backpack Elite":"Samsonite Ikonn Laptop Backpack",
    "Seiko DressKX Automatic Elite":        "Seiko 5 Sports Automatic",
    "Skybags Campus Daypack Value":         "Skybags Campus Daypack",
    "Sonata Essentials Analog Value":       "Sonata Essentials",
    "Sparx Mesh Runner Everyday":           "Sparx Running Shoes",
    "Tissot PRX Quartz Ultra":              "Tissot PRX",
    "Titan Neo Splash Pro":                 "Titan Neo Splash",
    "Tumi Alpha Bravo Backpack Ultra":      "Tumi Alpha Bravo",
    "Wildcraft Wiki Backpack Everyday":     "Wildcraft Wiki Backpack",
    "American Tourister Urban Pack Plus":   "American Tourister Urban Groove",

    # ── HOME APPLIANCES ─────────────────────────────────────────────────────────
    "AGARO Regal Plus Pro":                 "AGARO Regal Plus",
    "Bajaj Rex 500W Value":                 "Bajaj Rex 500W",
    "Bosch TrueMixx Pro Elite":             "Bosch TrueMixx Pro",
    "Butterfly Jet Elite Plus":             "Butterfly Jet Elite",
    "Dyson V12 Detect Slim Ultra":          "Dyson V12 Detect Slim",
    "Dyson V8 Absolute Elite":              "Dyson V8 Absolute",
    "Eureka Forbes Quick Clean DX Value":   "Eureka Forbes Quick Clean DX",
    "Havells Prolife Grande Pro":           "Havells Prolife Grande",
    "Instant Vortex Plus Elite":            "Instant Vortex Plus",
    "Karcher WD 1 Classic Everyday":        "Karcher WD 1 Classic",
    "KENT Classic Hot Air Fryer Everyday":  "KENT Classic Hot Air Fryer",
    "Ninja Foodi Dual Zone Ultra":          "Ninja Foodi Dual Zone",
    "Philips Essential Air Fryer Plus":     "Philips Essential Air Fryer HD9200",
    "Philips HL7756 Pro":                   "Philips HL7756",
    "Philips PowerPro Compact Plus":        "Philips PowerPro Compact",
    "Pigeon Healthifry 4L Value":           "Pigeon Healthifry 4L",
    "Prestige Iris Plus Everyday":          "Prestige Iris Plus",
    "Sujata Dynamix DX Ultra":              "Sujata Dynamix DX",

    # ── BOARD GAMES & TOYS ──────────────────────────────────────────────────────
    "Asmodee Splendor Plus":                "Splendor Board Game",
    "Bandai Anime Heroes Figure Pro":       "Bandai Anime Heroes",
    "Big Potato Herd Mentality Pro":        "Herd Mentality Board Game",
    "Cephalofair Gloomhaven Jaws Ultra":    "Gloomhaven Jaws of the Lion",
    "Codenames Pictures XXL Ultra":         "Codenames Pictures",
    "Days of Wonder Small World Pro":       "Small World Board Game",
    "Days of Wonder Ticket to Ride Ultra":  "Ticket to Ride Board Game",
    "Decathlon Kids Trampoline Pro":        "Decathlon Kids Trampoline",
    "Einstein Box Science Explorer Everyday":"Einstein Box Science Explorer",
    "Exploding Kittens Original Edition Everyday": "Exploding Kittens",
    "Funskool Hero Mini Figure Value":      "Funskool GI Joe Figure",
    "Funskool Ludo Classic Value":          "Funskool Ludo Classic",
    "Hasbro Marvel Titan Hero Everyday":    "Hasbro Marvel Titan Hero",
    "Hasbro Monopoly Junior Everyday":      "Hasbro Monopoly Junior",
    "Hasbro Taboo Plus":                    "Hasbro Taboo",
    "Hasbro The Game of Life Elite":        "Hasbro The Game of Life",
    "Hot Toys Collector Figure Ultra":      "Hot Toys Cosbaby Figure",
    "Kosmos Catan Junior Everyday":         "Catan Junior",
    "LEGO Education BricQ Set Pro":         "LEGO Education BricQ Motion",
    "Makeblock mBot Robot Kit Ultra":       "Makeblock mBot",
    "Mattel Jurassic World Dino Plus":      "Mattel Jurassic World Dinosaur",
    "Mattel UNO Party Plus":                "Mattel UNO",
    "McFarlane DC Multiverse Figure Elite": "McFarlane DC Multiverse",
    "Nerf Alpha Strike Blaster Value":      "Nerf Alpha Strike",
    "PlayShifu Tacto Coding Plus":          "PlayShifu Tacto Coding",
    "R for Rabbit Scooter Junior Plus":     "R for Rabbit Scooter Junior",
    "Repos Just One Elite":                 "Just One Card Game",
    "Segway Ninebot Kids Scooter Ultra":    "Segway Ninebot eKickScooter",
    "Smartivity Hydraulic Crane Kit Value": "Smartivity Hydraulic Crane Kit",
    "Sphero Mini Coding Robot Elite":       "Sphero Mini",
    "Spin Master Hedbanz Pro":              "Spin Master Hedbanz",
    "Stonemaier Rolling Realms Value":      "Stonemaier Rolling Realms",
    "Stonemaier Wingspan Elite":            "Wingspan Board Game",
    "Taco Cat Goat Card Game Value":        "Taco Cat Goat Cheese Pizza",
    "Toyshine Bubble Machine Everyday":     "Toyshine Bubble Machine",
    "VTech KidiZoom Camera Elite":          "VTech KidiZoom Camera",

    # ── COVERS & CASES ──────────────────────────────────────────────────────────
    "AmazonBasics Neoprene Sleeve Value":   "AmazonBasics Neoprene Laptop Sleeve",
    "CaseMate Clear Shield Case Value":     "Case-Mate Clear Shield",
    "DailyObjects Silicone Grip Case Everyday": "DailyObjects Silicone Grip Case",
    "DailyObjects Slim Sleeve Plus":        "DailyObjects Slim Sleeve",
    "ESR Rebound Folio Everyday":           "ESR Rebound Folio",
    "Lenovo Urban Sleeve Pro":              "Lenovo Urban Sleeve",
    "Mous Limitless Aramid Case Ultra":     "Mous Limitless Aramid Case",
    "Native Union Stow Lite Sleeve Ultra":  "Native Union Stow Lite Sleeve",
    "OtterBox Defender Case Elite":         "OtterBox Defender",
    "ProElite Trifold Stand Cover Value":   "ProElite Trifold Stand Cover",
    "Ringke Fusion MagSafe Case Pro":       "Ringke Fusion MagSafe",
    "Spigen Rugged Armor Case Plus":        "Spigen Rugged Armor",
    "Spigen Urban Fit Cover Plus":          "Spigen Urban Fit",
    "tomtoc 360 Protective Sleeve Elite":   "tomtoc 360 Protective Sleeve",
    "Tukzer Canvas Sleeve Everyday":        "Tukzer Canvas Sleeve",
    "ZAGG Rugged Book Cover Ultra":         "ZAGG Rugged Book",
}

# ─── True duplicates to DELETE (title of the one to remove) ─────────────────────
# Keep the better/original one, delete the synthetic duplicate.
DUPLICATES_TO_DELETE = {
    "OnePlus 12 Everyday",        # keep "OnePlus 12"
    "OnePlus Nord CE4 Everyday",  # keep "OnePlus Nord CE4"
}


# ─── Shopify helpers ─────────────────────────────────────────────────────────────

async def get_all_products(client):
    products = []
    page_info = None
    while True:
        url = f"{BASE}/products.json?limit=250&fields=id,title"
        if page_info:
            url += f"&page_info={page_info}"
        r = await client.get(url, headers=H)
        r.raise_for_status()
        products.extend(r.json().get("products", []))
        link = r.headers.get("Link", "")
        if 'rel="next"' in link:
            for part in link.split(","):
                if 'rel="next"' in part:
                    for param in part.split(";")[0].strip().strip("<>").split("&"):
                        if param.startswith("page_info="):
                            page_info = param.split("=", 1)[1]
                            break
                    break
        else:
            break
    return products


async def rename_product(client, pid, new_title, dry_run):
    if dry_run:
        return True
    r = await client.put(
        f"{BASE}/products/{pid}.json",
        headers=H,
        json={"product": {"id": pid, "title": new_title}},
        timeout=15,
    )
    return r.status_code == 200


async def delete_product(client, pid, dry_run):
    if dry_run:
        return True
    r = await client.delete(f"{BASE}/products/{pid}.json", headers=H, timeout=15)
    return r.status_code == 200


# ─── Main ────────────────────────────────────────────────────────────────────────

async def main(dry_run=False):
    if not STORE or not TOKEN:
        print("ERROR: missing env vars"); sys.exit(1)

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Fetching products...")

    async with httpx.AsyncClient(timeout=30) as client:
        products = await get_all_products(client)

    title_to_id = {p["title"]: p["id"] for p in products}

    renamed = 0
    deleted = 0
    skipped = 0
    not_found = []

    print(f"\nTotal products: {len(products)}")
    print(f"Renames queued: {len(RENAMES)}")
    print(f"Deletes queued: {len(DUPLICATES_TO_DELETE)}\n")

    async with httpx.AsyncClient(timeout=30) as client:

        # 1. Renames
        for old_title, new_title in RENAMES.items():
            pid = title_to_id.get(old_title)
            if not pid:
                not_found.append(old_title)
                continue
            if old_title == new_title:
                skipped += 1
                continue
            print(f"  RENAME: {old_title!r}")
            print(f"       -> {new_title!r}")
            ok = await rename_product(client, pid, new_title, dry_run)
            if ok:
                renamed += 1
            else:
                print(f"  FAIL renaming {old_title}")
            await asyncio.sleep(0.4)

        # 2. Deletes
        for title in DUPLICATES_TO_DELETE:
            pid = title_to_id.get(title)
            if not pid:
                not_found.append(title)
                continue
            print(f"  DELETE duplicate: {title!r}")
            ok = await delete_product(client, pid, dry_run)
            if ok:
                deleted += 1
            else:
                print(f"  FAIL deleting {title}")
            await asyncio.sleep(0.4)

    print(f"\n{'-'*55}")
    print(f"Renamed: {renamed}   Deleted: {deleted}   Skipped: {skipped}")
    if not_found:
        print(f"\nNot found in store ({len(not_found)}) — already renamed or doesn't exist:")
        for t in not_found:
            print(f"  - {t}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without changing anything")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
