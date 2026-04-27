"""
populate_shopify.py — Bulk-create synthetic products in your Shopify dev store.

Usage:
    cd backend
    python scripts/populate_shopify.py

Requires:
    SHOPIFY_STORE_URL   = yourstore.myshopify.com
    SHOPIFY_ADMIN_TOKEN = shpat_xxxxxxxxxxxxxxxxxxxx

Creates ~90 products across 5 categories with realistic:
  - Prices (INR)
  - Tags (brand, use-case, features)
  - Descriptions
  - Metafields: rating, review_count, review_highlight
"""

import asyncio
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

_STORE_URL   = os.getenv("SHOPIFY_STORE_URL", "").strip().rstrip("/")
_ADMIN_TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN", "").strip()
_API_VERSION = "2025-01"
_ENDPOINT    = f"https://{_STORE_URL}/admin/api/{_API_VERSION}/graphql.json"
_HEADERS     = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": _ADMIN_TOKEN,
}

_CREATE_PRODUCT = """
mutation ProductCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
    }
    userErrors {
      field
      message
    }
  }
}
"""

# ─── Product catalog ────────────────────────────────────────────────────────────

PRODUCTS = [

    # ── RUNNING SHOES ────────────────────────────────────────────────────────────

    {
        "title": "Nike Air Zoom Pegasus 40",
        "vendor": "Nike",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "nike", "cushioning", "daily-trainer", "men"],
        "description": "The Nike Air Zoom Pegasus 40 is the go-to daily trainer for road runners. Zoom Air cushioning delivers a responsive, springy ride while the breathable mesh upper keeps your foot cool on long runs. Ideal for everyday training and race days.",
        "price": 8995,
        "rating": 4.6, "review_count": 3842, "review_highlight": "Best road shoe I've owned — incredibly smooth on tarmac."
    },
    {
        "title": "Nike React Infinity Run Flyknit 3",
        "vendor": "Nike",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "nike", "stability", "injury-prevention", "flat-feet-support"],
        "description": "Designed to reduce injury risk for road runners. Wide, rocker-shaped sole helps guide your foot through each stride. Nike React foam provides maximum cushioning — ideal for runners with flat feet or overpronation.",
        "price": 10995,
        "rating": 4.5, "review_count": 2107, "review_highlight": "My physio recommended these — zero knee pain since switching."
    },
    {
        "title": "Adidas Ultraboost 23",
        "vendor": "Adidas",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "adidas", "boost-cushioning", "energy-return", "daily-trainer"],
        "description": "Boost midsole technology stores and returns energy with every stride. Primeknit+ upper wraps your foot like a second skin. Premium road running shoe for those who want speed without sacrificing comfort.",
        "price": 12999,
        "rating": 4.7, "review_count": 5210, "review_highlight": "Energy return is unreal — felt fresh even at kilometre 20."
    },
    {
        "title": "Adidas Solarboost 5",
        "vendor": "Adidas",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "adidas", "lightweight", "stability", "men"],
        "description": "Lightweight road running shoe with targeted banding for midfoot support. Boost midsole for responsive cushioning. Great choice for tempo runs and long-distance training.",
        "price": 8499,
        "rating": 4.4, "review_count": 987, "review_highlight": "Surprised by how light they feel — great for speed work."
    },
    {
        "title": "Skechers GOrun Ride 10",
        "vendor": "Skechers",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "skechers", "lightweight", "budget", "daily-trainer", "flat-feet-support"],
        "description": "Ultra-lightweight road runner with 5GEN cushioning. Mesh upper provides ventilation. Excellent value for beginner and intermediate runners training on roads. Wide toe-box suits flat feet.",
        "price": 4499,
        "rating": 4.3, "review_count": 4521, "review_highlight": "Perfect beginner shoe — comfortable right out of the box."
    },
    {
        "title": "Skechers GOrun Consistent 2.0",
        "vendor": "Skechers",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "skechers", "cushioning", "budget", "women"],
        "description": "Responsive 5GEN cushioning for road running. Flexible, lightweight upper with a seamless design. Ideal for women looking for an affordable daily trainer.",
        "price": 3799,
        "rating": 4.2, "review_count": 2891, "review_highlight": "So comfortable for everyday running — great price too."
    },
    {
        "title": "New Balance Fresh Foam X 1080v13",
        "vendor": "New Balance",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "new-balance", "max-cushioning", "long-distance", "premium"],
        "description": "Maximum cushioning for long-distance road running. Fresh Foam X midsole delivers plush underfoot feel. Hypoknit upper adapts to foot movement. Best-in-class comfort for half marathons and beyond.",
        "price": 14999,
        "rating": 4.8, "review_count": 1634, "review_highlight": "The most comfortable road shoe I've ever run in. Period."
    },
    {
        "title": "New Balance FuelCell Rebel v3",
        "vendor": "New Balance",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "new-balance", "speed", "lightweight", "tempo"],
        "description": "Speed-oriented FuelCell foam for fast road running. Lightweight and responsive — perfect for tempo runs and 5K/10K races. For neutral runners looking for a performance edge.",
        "price": 9999,
        "rating": 4.5, "review_count": 876, "review_highlight": "Shaved 45 seconds off my 5K PB. Phenomenal speed shoe."
    },
    {
        "title": "Puma Velocity Nitro 2",
        "vendor": "Puma",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "puma", "nitro-foam", "daily-trainer", "budget"],
        "description": "NITRO foam midsole offers an excellent weight-to-cushioning ratio. Engineered mesh upper for breathability. Great everyday road shoe at a mid-range price.",
        "price": 6999,
        "rating": 4.4, "review_count": 1423, "review_highlight": "Outperforms shoes twice its price — NITRO foam is excellent."
    },
    {
        "title": "Reebok Forever Floatride Energy 5",
        "vendor": "Reebok",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "reebok", "floatride", "cushioning", "daily-trainer"],
        "description": "Floatride Energy foam delivers a lightweight yet cushioned ride for road runners. Durable rubber outsole for all-weather traction. Ideal for daily training runs.",
        "price": 5999,
        "rating": 4.2, "review_count": 763, "review_highlight": "Solid workhorse shoe — not flashy but super reliable."
    },
    {
        "title": "Brooks Ghost 15",
        "vendor": "Brooks",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "road-running", "brooks", "neutral", "cushioning", "versatile"],
        "description": "Iconic neutral daily trainer from Brooks. DNA LOFT v3 foam for soft cushioning. Accommodating fit works for a wide range of foot shapes including flat feet.",
        "price": 11999,
        "rating": 4.7, "review_count": 6847, "review_highlight": "The most consistent shoe I've trained in for 3 years running."
    },
    {
        "title": "Adidas Terrex Trailmaker 2",
        "vendor": "Adidas",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "trail-running", "adidas", "grip", "waterproof", "outdoor"],
        "description": "Built for trail running on technical terrain. Continental™ rubber outsole for multi-surface grip. Waterproof GORE-TEX lining keeps feet dry in wet conditions.",
        "price": 9499,
        "rating": 4.5, "review_count": 521, "review_highlight": "Handled the Western Ghats trails like a dream. Zero slips."
    },
    {
        "title": "Nike Wildhorse 7",
        "vendor": "Nike",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "trail-running", "nike", "grip", "durable", "outdoor"],
        "description": "Rugged trail running shoe with multi-directional traction lugs for off-road grip. Rock plate protects against sharp surfaces. Durable for technical hill runs.",
        "price": 7499,
        "rating": 4.3, "review_count": 389, "review_highlight": "Aggressive grip — I can confidently run in the mud now."
    },
    {
        "title": "Skechers GOtrain Hyper Burst",
        "vendor": "Skechers",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "gym", "training", "skechers", "lightweight", "cross-training"],
        "description": "Ultra-lightweight training shoe with Hyper Burst cushioning. Low-profile design for gym workouts, HIIT, and strength training. Flexible sole for multi-directional movement.",
        "price": 3299,
        "rating": 4.1, "review_count": 1897, "review_highlight": "My new gym shoe — light, stable, and doesn't feel bulky at all."
    },
    {
        "title": "Nike Metcon 8",
        "vendor": "Nike",
        "product_type": "Running Shoes",
        "tags": ["running-shoes", "gym", "cross-training", "nike", "stability", "weightlifting"],
        "description": "Nike's premier cross-training shoe. Flat, stable heel for lifting; flexible forefoot for sprints and jumps. The go-to for gym, CrossFit, and functional fitness training.",
        "price": 9995,
        "rating": 4.6, "review_count": 2341, "review_highlight": "Does everything in the gym — squats, box jumps, short runs."
    },

    # ── SKINCARE ─────────────────────────────────────────────────────────────────

    {
        "title": "The Ordinary Niacinamide 10% + Zinc 1%",
        "vendor": "The Ordinary",
        "product_type": "Skincare",
        "tags": ["skincare", "serum", "oily-skin", "acne-prone", "pores", "niacinamide", "budget"],
        "description": "High-strength niacinamide serum reduces the appearance of blemishes, pores, and excess oil. Zinc balances sebum production. Ideal for oily and acne-prone skin types.",
        "price": 690,
        "rating": 4.6, "review_count": 8923, "review_highlight": "Cleared my forehead acne in 3 weeks. Cult product for a reason."
    },
    {
        "title": "Minimalist 2% Salicylic Acid Serum",
        "vendor": "Minimalist",
        "product_type": "Skincare",
        "tags": ["skincare", "serum", "oily-skin", "acne-prone", "salicylic-acid", "exfoliating"],
        "description": "BHA serum that penetrates into pores to clear blackheads and prevent acne. Lightweight oil-free formula ideal for oily and combination skin. Targets active breakouts and prevents new ones.",
        "price": 549,
        "rating": 4.5, "review_count": 6231, "review_highlight": "Best salicylic acid product I've used — blackheads reduced in 10 days."
    },
    {
        "title": "Minimalist SPF 50 PA++++ Sunscreen",
        "vendor": "Minimalist",
        "product_type": "Skincare",
        "tags": ["skincare", "sunscreen", "oily-skin", "spf50", "lightweight", "non-greasy"],
        "description": "Broad-spectrum SPF 50 PA++++ sunscreen with no white cast. Water-based formula ideal for oily skin in Indian summers. Non-comedogenic and dermatologically tested.",
        "price": 399,
        "rating": 4.7, "review_count": 12087, "review_highlight": "Finally a sunscreen that doesn't make my face look like a disco ball."
    },
    {
        "title": "Dot & Key Waterlight Gel Moisturiser",
        "vendor": "Dot & Key",
        "product_type": "Skincare",
        "tags": ["skincare", "moisturizer", "oily-skin", "combination-skin", "lightweight", "gel", "oil-free"],
        "description": "Oil-free gel moisturiser for oily and combination skin. Hydrates without clogging pores. 72-hour moisture lock with Hyaluronic Acid and Niacinamide. Perfect for humid Indian weather.",
        "price": 699,
        "rating": 4.5, "review_count": 4312, "review_highlight": "Doesn't feel heavy at all — skin feels fresh and matte all day."
    },
    {
        "title": "Plum E-Luminence Simply Light Lotion",
        "vendor": "Plum",
        "product_type": "Skincare",
        "tags": ["skincare", "moisturizer", "dry-skin", "vitamin-e", "nourishing", "lightweight"],
        "description": "Vitamin E and plant extracts deeply nourish dry skin without greasiness. Fast-absorbing formula that leaves skin soft and radiant. Suitable for normal to dry skin types.",
        "price": 399,
        "rating": 4.4, "review_count": 2891, "review_highlight": "My dry skin finally feels plump after using this for a month."
    },
    {
        "title": "Cetaphil Moisturizing Cream",
        "vendor": "Cetaphil",
        "product_type": "Skincare",
        "tags": ["skincare", "moisturizer", "dry-skin", "sensitive-skin", "fragrance-free", "dermatologist-recommended"],
        "description": "Rich, non-greasy moisturiser for dry and sensitive skin. Fragrance-free, non-comedogenic formula. Dermatologist recommended for eczema-prone and very dry skin. 48-hour moisture barrier.",
        "price": 849,
        "rating": 4.8, "review_count": 15632, "review_highlight": "Dermatologist recommended this and it changed my winter skincare forever."
    },
    {
        "title": "The Ordinary Hyaluronic Acid 2% + B5",
        "vendor": "The Ordinary",
        "product_type": "Skincare",
        "tags": ["skincare", "serum", "dry-skin", "hydration", "hyaluronic-acid", "plumping"],
        "description": "Multi-weight hyaluronic acid for deep and surface hydration. Vitamin B5 supports skin healing. Ideal for dry and dehydrated skin — gives an instant plumping effect.",
        "price": 750,
        "rating": 4.6, "review_count": 7841, "review_highlight": "Skin looks visibly plumper after just one week. Love it."
    },
    {
        "title": "Minimalist 10% Vitamin C Serum",
        "vendor": "Minimalist",
        "product_type": "Skincare",
        "tags": ["skincare", "serum", "brightening", "vitamin-c", "anti-aging", "all-skin-types"],
        "description": "Ethyl Ascorbic Acid (stable Vitamin C) at 10% concentration for visible brightening. Reduces dark spots, hyperpigmentation, and dullness. Suitable for all skin types.",
        "price": 599,
        "rating": 4.5, "review_count": 5432, "review_highlight": "My dark spots from old acne have faded noticeably in 6 weeks."
    },
    {
        "title": "Mamaearth Ubtan Face Wash",
        "vendor": "Mamaearth",
        "product_type": "Skincare",
        "tags": ["skincare", "face-wash", "oily-skin", "turmeric", "natural", "brightening"],
        "description": "Turmeric and saffron face wash that brightens skin while removing excess oil and impurities. No harmful chemicals. Suitable for oily and normal skin types.",
        "price": 249,
        "rating": 4.3, "review_count": 9823, "review_highlight": "Makes my skin glow — and the price is unbeatable."
    },
    {
        "title": "Bioderma Sensibio H2O Micellar Water",
        "vendor": "Bioderma",
        "product_type": "Skincare",
        "tags": ["skincare", "cleanser", "sensitive-skin", "makeup-remover", "gentle", "fragrance-free"],
        "description": "Iconic French micellar water that gently removes makeup and cleanses sensitive skin without rinsing. Ophthalmologist tested. No drying effect.",
        "price": 1099,
        "rating": 4.7, "review_count": 11234, "review_highlight": "Removes even waterproof mascara without any irritation."
    },
    {
        "title": "Forest Essentials Facial Ubtan",
        "vendor": "Forest Essentials",
        "product_type": "Skincare",
        "tags": ["skincare", "cleanser", "dry-skin", "ayurvedic", "natural", "brightening", "premium"],
        "description": "Traditional Ayurvedic ubtan with milk proteins, saffron, and herbs. Gently exfoliates while brightening and nourishing dry skin. Luxurious Ayurvedic skincare.",
        "price": 1295,
        "rating": 4.5, "review_count": 1876, "review_highlight": "Skin looks brighter and feels incredibly soft after one week."
    },
    {
        "title": "Neutrogena Hydro Boost Water Gel",
        "vendor": "Neutrogena",
        "product_type": "Skincare",
        "tags": ["skincare", "moisturizer", "combination-skin", "hyaluronic-acid", "lightweight", "oil-free"],
        "description": "Clinically proven hyaluronic acid gel moisturiser. Instantly quenches dry skin and keeps it hydrated for 48 hours. Lightweight, oil-free formula suitable for combination skin.",
        "price": 999,
        "rating": 4.6, "review_count": 8765, "review_highlight": "Best gel moisturiser — absorbs instantly and lasts all day."
    },
    {
        "title": "Plum Green Tea Pore Cleansing Face Scrub",
        "vendor": "Plum",
        "product_type": "Skincare",
        "tags": ["skincare", "exfoliator", "oily-skin", "green-tea", "pores", "natural"],
        "description": "Physical exfoliator with green tea extract and botanical beads. Unclogs pores and removes dead skin cells without over-stripping. Vegan and 100% toxin-free.",
        "price": 345,
        "rating": 4.3, "review_count": 3421, "review_highlight": "Great for pre-event skin prep — leaves my skin baby smooth."
    },
    {
        "title": "Kiehl's Ultra Facial Cream SPF 30",
        "vendor": "Kiehl's",
        "product_type": "Skincare",
        "tags": ["skincare", "moisturizer", "sunscreen", "dry-skin", "premium", "spf30", "all-day-hydration"],
        "description": "Premium daily moisturiser with SPF 30 protection. Squalane and glacial glycoprotein provide intense long-lasting hydration. Suitable for dry to normal skin.",
        "price": 3200,
        "rating": 4.6, "review_count": 2341, "review_highlight": "One product does it all — moisture + sun protection. Worth every rupee."
    },
    {
        "title": "Innisfree Green Tea Seed Serum",
        "vendor": "Innisfree",
        "product_type": "Skincare",
        "tags": ["skincare", "serum", "hydration", "green-tea", "brightening", "all-skin-types"],
        "description": "Jeju green tea seed extract serum that provides moisture and antioxidant protection. Lightweight formula that layers well with other serums. Suitable for all skin types.",
        "price": 1499,
        "rating": 4.5, "review_count": 3876, "review_highlight": "My skin is softer than ever — can't imagine my routine without it."
    },

    # ── SMARTPHONES ──────────────────────────────────────────────────────────────

    {
        "title": "Samsung Galaxy S24",
        "vendor": "Samsung",
        "product_type": "Smartphone",
        "tags": ["smartphone", "samsung", "android", "5g", "camera", "ai", "premium", "amoled"],
        "description": "Galaxy AI features, ProVisual Engine for stunning 50MP photography, and 7 years of OS updates. Snapdragon 8 Gen 3 chipset. Bright 6.2-inch Dynamic AMOLED 2X display with 120Hz refresh rate.",
        "price": 74999,
        "rating": 4.6, "review_count": 4521, "review_highlight": "Galaxy AI is actually useful — the camera quality is insane at night."
    },
    {
        "title": "OnePlus 12",
        "vendor": "OnePlus",
        "product_type": "Smartphone",
        "tags": ["smartphone", "oneplus", "android", "5g", "camera", "fast-charging", "hasselblad", "gaming"],
        "description": "Snapdragon 8 Gen 3, Hasselblad-tuned 50MP triple camera, 100W SUPERVOOC fast charging. 6.82-inch AMOLED display at 120Hz with 4500 nits peak brightness. Gaming-grade performance.",
        "price": 64999,
        "rating": 4.7, "review_count": 3214, "review_highlight": "Charges from 0 to 100% in 28 minutes. The speed is addictive."
    },
    {
        "title": "Xiaomi 14",
        "vendor": "Xiaomi",
        "product_type": "Smartphone",
        "tags": ["smartphone", "xiaomi", "android", "5g", "leica-camera", "camera", "premium", "performance"],
        "description": "Leica co-engineered triple camera with 50MP main sensor. Snapdragon 8 Gen 3 flagship chipset. 6.36-inch AMOLED with 120Hz. 90W HyperCharge for full battery in 31 minutes.",
        "price": 59999,
        "rating": 4.5, "review_count": 2187, "review_highlight": "Leica camera is stunning — portrait mode looks like a DSLR shot."
    },
    {
        "title": "Realme GT 6",
        "vendor": "Realme",
        "product_type": "Smartphone",
        "tags": ["smartphone", "realme", "android", "5g", "performance", "gaming", "budget-flagship"],
        "description": "Snapdragon 8s Gen 3 processor for flagship gaming performance at mid-range price. 120Hz SuperAMOLED display, 5000mAh battery with 120W fast charging.",
        "price": 39999,
        "rating": 4.4, "review_count": 1643, "review_highlight": "Best value flagship — gaming performance rivals phones twice the price."
    },
    {
        "title": "Samsung Galaxy A55 5G",
        "vendor": "Samsung",
        "product_type": "Smartphone",
        "tags": ["smartphone", "samsung", "android", "5g", "camera", "mid-range", "durable"],
        "description": "Samsung's best mid-range with IP67 water resistance, 50MP OIS camera, and 6.6-inch Super AMOLED. Exynos 1480 chipset. 4 years of OS updates. Gorilla Glass Victus+.",
        "price": 38999,
        "rating": 4.5, "review_count": 5432, "review_highlight": "Water resistant at this price point? Samsung, you legend."
    },
    {
        "title": "Xiaomi Redmi Note 13 Pro+ 5G",
        "vendor": "Xiaomi",
        "product_type": "Smartphone",
        "tags": ["smartphone", "xiaomi", "redmi", "android", "5g", "camera", "mid-range", "battery"],
        "description": "200MP main camera at mid-range pricing. Dimensity 7200-Ultra chipset, 6.67-inch AMOLED at 120Hz, 5000mAh battery with 120W charging. IP68 water resistance.",
        "price": 29999,
        "rating": 4.4, "review_count": 7823, "review_highlight": "200MP camera for 30K is unheard of — night shots are incredible."
    },
    {
        "title": "OnePlus Nord CE4",
        "vendor": "OnePlus",
        "product_type": "Smartphone",
        "tags": ["smartphone", "oneplus", "android", "5g", "battery", "fast-charging", "mid-range"],
        "description": "Snapdragon 7s Gen 2, 6.7-inch AMOLED 120Hz display, 5000mAh battery with 100W SUPERVOOC charging. OxygenOS 14 for clean software experience. Under 25K.",
        "price": 24999,
        "rating": 4.3, "review_count": 3218, "review_highlight": "OxygenOS is still the cleanest Android skin. Great daily driver."
    },
    {
        "title": "Samsung Galaxy A35 5G",
        "vendor": "Samsung",
        "product_type": "Smartphone",
        "tags": ["smartphone", "samsung", "android", "5g", "mid-range", "camera", "battery"],
        "description": "Exynos 1380 chipset with 50MP OIS camera. 6.6-inch Super AMOLED at 120Hz. IP67, Gorilla Glass Victus+. 5000mAh battery. 4 years OS + 5 years security updates.",
        "price": 26999,
        "rating": 4.4, "review_count": 4521, "review_highlight": "Solid all-rounder with Samsung's promise of 4 years updates."
    },
    {
        "title": "Realme Narzo 70 Pro 5G",
        "vendor": "Realme",
        "product_type": "Smartphone",
        "tags": ["smartphone", "realme", "android", "5g", "battery", "budget", "photography"],
        "description": "Dimensity 7050 chipset with 50MP Sony IMX890 camera. 6.7-inch AMOLED 120Hz display. 5000mAh battery with 67W fast charging. Excellent budget-friendly performer.",
        "price": 17999,
        "rating": 4.2, "review_count": 2341, "review_highlight": "Sony sensor at this price is a steal — great for daily photography."
    },
    {
        "title": "Google Pixel 8a",
        "vendor": "Google",
        "product_type": "Smartphone",
        "tags": ["smartphone", "google", "pixel", "android", "5g", "camera", "ai", "clean-android", "photography"],
        "description": "Google Tensor G3 chip with Google AI features. Best-in-class computational photography. Guaranteed 7 years of Android updates. 6.1-inch OLED display. Magic Eraser, Best Take, Audio Magic Eraser.",
        "price": 52999,
        "rating": 4.7, "review_count": 1876, "review_highlight": "The AI photo features feel like actual magic — especially Best Take."
    },

    # ── LAPTOPS ──────────────────────────────────────────────────────────────────

    {
        "title": "ASUS ROG Strix G16 Gaming Laptop",
        "vendor": "ASUS",
        "product_type": "Laptop",
        "tags": ["laptop", "gaming", "asus", "rog", "nvidia", "rtx4070", "gpu", "144hz", "dedicated-graphics", "performance"],
        "description": "Intel Core i7-13650HX + NVIDIA RTX 4070 8GB GPU. 16-inch QHD 165Hz IPS display. 16GB DDR5 RAM, 512GB NVMe SSD. MUX Switch, ROG Boost for peak gaming performance.",
        "price": 124999,
        "rating": 4.6, "review_count": 1234, "review_highlight": "RTX 4070 in a laptop — runs everything at ultra settings without breaking a sweat."
    },
    {
        "title": "Lenovo LOQ 15 Gaming Laptop",
        "vendor": "Lenovo",
        "product_type": "Laptop",
        "tags": ["laptop", "gaming", "lenovo", "nvidia", "rtx4060", "gpu", "144hz", "budget-gaming", "dedicated-graphics"],
        "description": "Intel Core i5-13420H + NVIDIA RTX 4060 laptop GPU. 15.6-inch FHD 144Hz display. 16GB DDR5, 512GB SSD. Excellent budget gaming laptop for 1080p gaming at high settings.",
        "price": 74999,
        "rating": 4.5, "review_count": 2341, "review_highlight": "Best gaming laptop under 75K — RTX 4060 handles every game beautifully."
    },
    {
        "title": "HP Victus 16 Gaming Laptop",
        "vendor": "HP",
        "product_type": "Laptop",
        "tags": ["laptop", "gaming", "hp", "nvidia", "rtx4050", "gpu", "144hz", "budget-gaming", "dedicated-graphics"],
        "description": "AMD Ryzen 7 7745HX + NVIDIA RTX 4050 6GB. 16.1-inch FHD 144Hz display. 16GB DDR5 RAM, 512GB PCIe SSD. Great gaming performance for mid-range budget.",
        "price": 64999,
        "rating": 4.4, "review_count": 1876, "review_highlight": "Runs Valorant and GTA V at ultra settings smoothly. Happy with the purchase."
    },
    {
        "title": "Dell Inspiron 16 Plus",
        "vendor": "Dell",
        "product_type": "Laptop",
        "tags": ["laptop", "work", "dell", "intel", "16inch", "display", "productivity", "student", "office"],
        "description": "Intel Core i7-13700H + Intel Arc A530M GPU. 16-inch 3K IPS display. 16GB DDR5, 512GB SSD. Excellent for students, creators, and professionals who need a large display.",
        "price": 69999,
        "rating": 4.4, "review_count": 987, "review_highlight": "The 3K display is stunning for video editing and document work."
    },
    {
        "title": "HP Envy x360 14",
        "vendor": "HP",
        "product_type": "Laptop",
        "tags": ["laptop", "work", "hp", "amd", "2-in-1", "touchscreen", "student", "lightweight", "oled"],
        "description": "AMD Ryzen 7 7730U + 2-in-1 form factor. 14-inch OLED touchscreen display. 16GB RAM, 512GB SSD. Lightweight at 1.46kg with up to 17 hours battery life. Perfect for students.",
        "price": 79999,
        "rating": 4.6, "review_count": 765, "review_highlight": "OLED display on a convertible laptop is a game-changer for note-taking and movies."
    },
    {
        "title": "Lenovo IdeaPad Slim 5",
        "vendor": "Lenovo",
        "product_type": "Laptop",
        "tags": ["laptop", "student", "lenovo", "lightweight", "battery", "amd", "budget", "office", "work"],
        "description": "AMD Ryzen 7 7730U processor. 15.6-inch FHD IPS display. 16GB RAM, 512GB SSD. Lightweight design with up to 12 hours battery life. Excellent student and everyday work laptop.",
        "price": 54999,
        "rating": 4.5, "review_count": 3421, "review_highlight": "Battery lasts through a full college day plus Netflix in the evening."
    },
    {
        "title": "ASUS Vivobook 16X",
        "vendor": "ASUS",
        "product_type": "Laptop",
        "tags": ["laptop", "student", "asus", "16inch", "performance", "budget", "amd", "office"],
        "description": "AMD Ryzen 9 7940HS + Radeon 780M integrated graphics. 16-inch WUXGA IPS display. 16GB DDR5, 512GB SSD. Powerful daily laptop for students and light creative work.",
        "price": 61999,
        "rating": 4.4, "review_count": 1234, "review_highlight": "AMD Ryzen 9 performance without a dedicated GPU price tag — great value."
    },
    {
        "title": "MSI Modern 14",
        "vendor": "MSI",
        "product_type": "Laptop",
        "tags": ["laptop", "work", "msi", "lightweight", "office", "intel", "thin", "professional"],
        "description": "Intel Core Ultra 5 125H. 14-inch FHD+ IPS display. 16GB LPDDR5, 512GB NVMe SSD. Ultra-thin design at 1.4kg. 12-hour battery life. Ideal for business professionals.",
        "price": 58999,
        "rating": 4.3, "review_count": 543, "review_highlight": "Travels with me everywhere — thin, light, and handles all my work tasks."
    },

    # ── HEADPHONES ───────────────────────────────────────────────────────────────

    {
        "title": "Sony WH-1000XM5",
        "vendor": "Sony",
        "product_type": "Headphones",
        "tags": ["headphones", "sony", "wireless", "noise-cancelling", "anc", "premium", "music", "travel"],
        "description": "Industry-leading noise cancellation with dual processor. 30-hour battery life, 3-min quick charge for 3 hours. Multipoint connection for 2 devices. Best ANC headphones available.",
        "price": 24990,
        "rating": 4.8, "review_count": 8921, "review_highlight": "ANC is so good it felt like I was in a silent room on a flight."
    },
    {
        "title": "Sony WH-1000XM4",
        "vendor": "Sony",
        "product_type": "Headphones",
        "tags": ["headphones", "sony", "wireless", "noise-cancelling", "anc", "premium", "music", "travel"],
        "description": "Previous gen flagship with best-in-class noise cancellation. 30-hour battery, multipoint pairing, Speak-to-Chat. Often available at a significant discount over XM5.",
        "price": 19990,
        "rating": 4.8, "review_count": 15234, "review_highlight": "Even one gen old, still the best ANC money can buy at this price."
    },
    {
        "title": "JBL Live 770NC",
        "vendor": "JBL",
        "product_type": "Headphones",
        "tags": ["headphones", "jbl", "wireless", "noise-cancelling", "anc", "music", "bass", "mid-range"],
        "description": "Adaptive noise cancelling with Smart Ambient. 65-hour battery life (ANC off). JBL Pure Bass Sound for powerful low-end. VoiceAware for natural conversation without removing headphones.",
        "price": 9999,
        "rating": 4.4, "review_count": 3421, "review_highlight": "65-hour battery is insane — I forget to charge it for days."
    },
    {
        "title": "Bose QuietComfort 45",
        "vendor": "Bose",
        "product_type": "Headphones",
        "tags": ["headphones", "bose", "wireless", "noise-cancelling", "anc", "premium", "comfort", "travel"],
        "description": "TriPort acoustic architecture with Bose proprietary ANC. 24-hour battery, ultra-lightweight design. Quiet and Aware Modes. Excellent for frequent flyers and office use.",
        "price": 29900,
        "rating": 4.7, "review_count": 5672, "review_highlight": "The most comfortable headphones I've ever worn — could use them for 8 hours straight."
    },
    {
        "title": "boAt Rockerz 550 Pro",
        "vendor": "boAt",
        "product_type": "Headphones",
        "tags": ["headphones", "boat", "wireless", "bass", "budget", "music", "gaming"],
        "description": "50mm custom drivers with boAt Signature Sound. 20-hour playback, fast charge. Foldable design for portability. Budget wireless headphones with punchy bass for casual listeners.",
        "price": 1299,
        "rating": 4.1, "review_count": 24321, "review_highlight": "Bass is powerful and sound is impressive for the price. Hard to beat at 1.3K."
    },
    {
        "title": "Sennheiser HD 450BT",
        "vendor": "Sennheiser",
        "product_type": "Headphones",
        "tags": ["headphones", "sennheiser", "wireless", "noise-cancelling", "balanced-sound", "music", "audiophile"],
        "description": "Active noise cancellation with Sennheiser's signature balanced sound profile. 30-hour battery. Foldable design. Excellent option for music purists who prefer accurate sound over boosted bass.",
        "price": 7999,
        "rating": 4.5, "review_count": 1876, "review_highlight": "Sennheiser audio quality at a reasonable price — instruments sound incredibly clear."
    },
    {
        "title": "Skullcandy Crusher Evo",
        "vendor": "Skullcandy",
        "product_type": "Headphones",
        "tags": ["headphones", "skullcandy", "wireless", "bass", "immersive", "music", "gaming", "mid-range"],
        "description": "Adjustable sensory bass with haptic feedback you can feel. Personal Sound with Audiodo. 40-hour battery. Rapid Charge. Best for bass-lovers and an immersive listening experience.",
        "price": 8499,
        "rating": 4.3, "review_count": 2341, "review_highlight": "The haptic bass is a completely different experience — incredible for EDM."
    },
    {
        "title": "OnePlus Buds Pro 2",
        "vendor": "OnePlus",
        "product_type": "Headphones",
        "tags": ["headphones", "earbuds", "oneplus", "wireless", "noise-cancelling", "anc", "music", "budget-premium"],
        "description": "Co-engineered with Dynaudio. Up to 48dB ANC, 11mm + 6mm dual drivers. Spatial audio. 39-hour total battery. Best ANC earbuds under 10K.",
        "price": 9499,
        "rating": 4.5, "review_count": 3218, "review_highlight": "Dynaudio-tuned sound is amazing — great ANC for the price point."
    },
    {
        "title": "Sony WF-1000XM5",
        "vendor": "Sony",
        "product_type": "Headphones",
        "tags": ["headphones", "earbuds", "sony", "wireless", "noise-cancelling", "anc", "premium", "compact"],
        "description": "World's best noise cancelling earbuds. V2 processor and integrated processor Q1. 8-hour battery + 24 hours with case. Crystal-clear call quality with 6 beamforming mics.",
        "price": 19990,
        "rating": 4.7, "review_count": 4532, "review_highlight": "ANC on these tiny earbuds rivals full-size headphones. Unbelievable."
    },
    {
        "title": "JBL Tune 770NC",
        "vendor": "JBL",
        "product_type": "Headphones",
        "tags": ["headphones", "jbl", "wireless", "noise-cancelling", "budget", "music", "bass"],
        "description": "Adaptive noise cancellation with JBL Pure Bass. 44-hour battery (ANC off). Foldable, lightweight design. Multi-point Bluetooth connection. Best budget ANC headphones.",
        "price": 4999,
        "rating": 4.3, "review_count": 5621, "review_highlight": "ANC headphones for 5K that actually work — JBL at their best value."
    },
]

# ─── Mutation helpers ───────────────────────────────────────────────────────────

_CREATE_MUTATION = """
mutation ProductCreate($input: ProductInput!) {
  productCreate(input: $input) {
    product {
      id
      title
    }
    userErrors {
      field
      message
    }
  }
}
"""

_PUBLISH_MUTATION = """
mutation PublishProduct($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) {
    publishable {
      ... on Product { id title }
    }
    userErrors {
      field
      message
    }
  }
}
"""

_METAFIELDS_MUTATION = """
mutation SetMetafields($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields {
      key
      value
    }
    userErrors {
      field
      message
    }
  }
}
"""


async def create_product(client: httpx.AsyncClient, product: dict) -> str | None:
    """Create one product. Returns product GID on success, None on error."""
    input_data = {
        "title": product["title"],
        "vendor": product.get("vendor", ""),
        "productType": product.get("product_type", ""),
        "tags": product.get("tags", []),
        "descriptionHtml": product.get("description", ""),
        "status": "ACTIVE",
        "variants": [
            {
                "price": str(product.get("price", 0)),
                "inventoryManagement": None,
                "taxable": False,
            }
        ],
    }

    resp = await client.post(
        _ENDPOINT,
        headers=_HEADERS,
        json={"query": _CREATE_MUTATION, "variables": {"input": input_data}},
    )
    resp.raise_for_status()
    data = resp.json()

    errors = data.get("data", {}).get("productCreate", {}).get("userErrors", [])
    if errors:
        print(f"  ✗  {product['title']}: {errors}")
        return None

    product_node = data.get("data", {}).get("productCreate", {}).get("product")
    if not product_node:
        print(f"  ✗  {product['title']}: no product in response")
        return None

    return product_node["id"]


async def set_metafields(client: httpx.AsyncClient, owner_id: str, product: dict) -> None:
    """Set rating/review_count/review_highlight metafields on a product."""
    metafields = []

    if product.get("rating"):
        metafields.append({
            "ownerId": owner_id,
            "namespace": "shopsense",
            "key": "rating",
            "value": str(product["rating"]),
            "type": "number_decimal",
        })

    if product.get("review_count"):
        metafields.append({
            "ownerId": owner_id,
            "namespace": "shopsense",
            "key": "review_count",
            "value": str(product["review_count"]),
            "type": "number_integer",
        })

    if product.get("review_highlight"):
        metafields.append({
            "ownerId": owner_id,
            "namespace": "shopsense",
            "key": "review_highlight",
            "value": product["review_highlight"],
            "type": "single_line_text_field",
        })

    if not metafields:
        return

    resp = await client.post(
        _ENDPOINT,
        headers=_HEADERS,
        json={"query": _METAFIELDS_MUTATION, "variables": {"metafields": metafields}},
    )
    resp.raise_for_status()
    data = resp.json()
    errors = data.get("data", {}).get("metafieldsSet", {}).get("userErrors", [])
    if errors:
        print(f"  ⚠  metafield errors for {owner_id}: {errors}")


# ─── Main ────────────────────────────────────────────────────────────────────────

async def main():
    if not _STORE_URL or not _ADMIN_TOKEN:
        print("ERROR: Set SHOPIFY_STORE_URL and SHOPIFY_ADMIN_TOKEN in backend/.env")
        sys.exit(1)

    print(f"🛍  Populating {_STORE_URL} with {len(PRODUCTS)} products…\n")

    created = 0
    failed  = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, product in enumerate(PRODUCTS, 1):
            print(f"[{i:02d}/{len(PRODUCTS)}] {product['title']} — ₹{product['price']:,}")

            product_id = await create_product(client, product)
            if product_id:
                await set_metafields(client, product_id, product)
                print(f"  ✓  created — {product_id}")
                created += 1
            else:
                failed += 1

            # Respect Shopify rate limit: 2 requests/second (cost-based)
            if i % 5 == 0:
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.5)

    print(f"\n{'─'*50}")
    print(f"✅  Created: {created}   ✗ Failed: {failed}")
    print(f"\nNext steps:")
    print(f"  1. Go to your Shopify admin → Products to verify")
    print(f"  2. Add product images manually (or via image URLs)")
    print(f"  3. Set SHOPIFY_ADMIN_TOKEN in Railway environment variables")


if __name__ == "__main__":
    asyncio.run(main())
