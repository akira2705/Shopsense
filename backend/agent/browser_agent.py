"""
Browser Agent — ShopSense's eyes on the web.

The AI controls a real browser, navigates to product sites,
takes a screenshot, and uses Groq Vision (llama-3.2-90b-vision-preview)
to read prices, ratings, and reviews — exactly like a human would.

Sites:
  - Amazon.in      → general products (electronics, shoes, skincare, gym, etc.)
  - Flipkart.com   → laptops, TVs, headphones, fashion, appliances
  - CarWale.com    → new cars / bikes research
  - OLX.in         → used / second-hand items (cars, bikes, phones, furniture)
"""

import base64
import json
import os
import re
from typing import Optional

# ── Demo fallback data (used when live browsing fails) ──────────────────────
# Realistic products per category so the demo never dead-ends.

_DEMO_PRODUCTS: dict[str, list[dict]] = {

    # ── New cars / bikes ────────────────────────────────────────────────────
    "carwale": [
        {
            "id": "cw_1", "title": "Maruti Suzuki Swift ZXi",
            "description": "2024 model, 1.2L petrol, 23.76 kmpl, 6 airbags, sunroof, Apple CarPlay",
            "tags": ["new", "car", "hatchback", "petrol", "maruti", "swift", "city", "daily"],
            "price": 899000, "rating": 4.5, "review_count": 8200,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/maruti-suzuki-cars/swift/",
        },
        {
            "id": "cw_2", "title": "Hyundai i20 Sportz 1.2 IVT",
            "description": "2024 model, automatic, 20.35 kmpl, 6 airbags, wireless charging, rear camera",
            "tags": ["new", "car", "hatchback", "petrol", "hyundai", "i20", "automatic", "city"],
            "price": 1020000, "rating": 4.4, "review_count": 5600,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/hyundai-cars/i20/",
        },
        {
            "id": "cw_3", "title": "Tata Punch Creative iCNG",
            "description": "2024 CNG, 26.99 km/kg, micro-SUV, high ground clearance, safety rated 5-star",
            "tags": ["new", "car", "suv", "cng", "tata", "punch", "city", "family"],
            "price": 820000, "rating": 4.3, "review_count": 4100,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/tata-cars/punch/",
        },
        {
            "id": "cw_4", "title": "Honda Amaze VX CVT Petrol",
            "description": "2024 sedan, automatic, 20.1 kmpl, rear AC, sunroof, lane-watch camera",
            "tags": ["new", "car", "sedan", "petrol", "honda", "amaze", "automatic", "family"],
            "price": 1220000, "rating": 4.4, "review_count": 3800,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/honda-cars/amaze/",
        },
        {
            "id": "cw_5", "title": "Maruti Suzuki Alto K10 VXi",
            "description": "2024, 1.0L petrol, 24.39 kmpl, lightest in segment, easy city driving",
            "tags": ["new", "car", "hatchback", "petrol", "maruti", "alto", "city", "budget"],
            "price": 540000, "rating": 4.1, "review_count": 11000,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/maruti-suzuki-cars/alto-k10/",
        },
        {
            "id": "cw_6", "title": "Bajaj Pulsar NS200 ABS",
            "description": "2024, 199.5cc, 24.5 bhp, liquid-cooled, single-channel ABS, sporty naked",
            "tags": ["new", "bike", "motorcycle", "bajaj", "pulsar", "sports", "commute"],
            "price": 153000, "rating": 4.5, "review_count": 7400,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/bajaj-bikes/pulsar-ns200/",
        },
        {
            "id": "cw_7", "title": "Hero Splendor+ XTEC",
            "description": "2024, 97.2cc, 60+ kmpl, USB charging, Bluetooth connectivity, most sold bike India",
            "tags": ["new", "bike", "motorcycle", "hero", "splendor", "commute", "mileage", "city"],
            "price": 82000, "rating": 4.3, "review_count": 22000,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/hero-bikes/splendor-plus/",
        },
        {
            "id": "cw_8", "title": "Hyundai Creta SX Petrol AT",
            "description": "2024 compact SUV, automatic, panoramic sunroof, ADAS safety, 17.4 kmpl",
            "tags": ["new", "car", "suv", "petrol", "hyundai", "creta", "automatic", "family", "highway"],
            "price": 1980000, "rating": 4.6, "review_count": 6100,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/hyundai-cars/creta/",
        },
        # 7-8 seater MPV / MUV
        {
            "id": "cw_9", "title": "Toyota Innova Crysta GX MT Diesel",
            "description": "2024, 7-seater MPV, 2.4L diesel, 15.1 kmpl, captain seats, most trusted family MPV",
            "tags": ["new", "car", "mpv", "muv", "7 seater", "7-seater", "diesel", "toyota", "innova", "family", "road trip", "highway", "spacious"],
            "price": 1990000, "rating": 4.7, "review_count": 14200,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/toyota-cars/innova-crysta/",
        },
        {
            "id": "cw_10", "title": "Maruti Suzuki Ertiga VXi CNG",
            "description": "2024, 7-seater MPV, CNG + petrol, 26.11 km/kg, best-value people carrier",
            "tags": ["new", "car", "mpv", "7 seater", "7-seater", "cng", "maruti", "ertiga", "family", "spacious", "budget"],
            "price": 1070000, "rating": 4.3, "review_count": 9800,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/maruti-suzuki-cars/ertiga/",
        },
        {
            "id": "cw_11", "title": "Kia Carens Prestige+ 7-Seat Diesel AT",
            "description": "2024, 7-seater, automatic, panoramic sunroof, ADAS, 360 camera, premium MPV",
            "tags": ["new", "car", "mpv", "7 seater", "7-seater", "diesel", "kia", "carens", "automatic", "family", "premium"],
            "price": 2030000, "rating": 4.5, "review_count": 6700,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/kia-cars/carens/",
        },
        {
            "id": "cw_12", "title": "Toyota Fortuner Legender 4x2 AT",
            "description": "2024, 7-seater SUV, 2.8L diesel, 10 kmpl, legendary off-road, full-size body-on-frame",
            "tags": ["new", "car", "suv", "7 seater", "7-seater", "diesel", "toyota", "fortuner", "automatic", "premium", "highway", "off road"],
            "price": 4650000, "rating": 4.8, "review_count": 5200,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/toyota-cars/fortuner/",
        },
        {
            "id": "cw_13", "title": "Mahindra XUV700 AX7 7-Seat Diesel AT",
            "description": "2024, 7-seater, ADAS Level 2, panoramic sunroof, 360 camera, 18.15 kmpl",
            "tags": ["new", "car", "suv", "7 seater", "7-seater", "diesel", "mahindra", "xuv700", "automatic", "family", "premium", "highway"],
            "price": 2690000, "rating": 4.6, "review_count": 8400,
            "image_url": None, "variant_id": None, "source": "carwale",
            "url": "https://www.carwale.com/mahindra-cars/xuv700/",
        },
    ],

    # ── Used / second-hand items ─────────────────────────────────────────────
    "olx": [
        {
            "id": "olx_c1", "title": "Maruti Suzuki Swift VDi — 2019",
            "description": "45000 km, first owner, diesel, excellent condition, all papers clear",
            "tags": ["used", "car", "hatchback", "diesel", "maruti", "swift", "second hand"],
            "price": 480000, "rating": 4.3, "review_count": None,
            "image_url": None, "variant_id": None, "source": "olx",
            "url": "https://www.olx.in/cars_c84",
        },
        {
            "id": "olx_c2", "title": "Hyundai i20 Sportz 2018 Petrol",
            "description": "52000 km, second owner, petrol, new tyres, accident-free",
            "tags": ["used", "car", "hatchback", "petrol", "hyundai", "i20", "second hand"],
            "price": 450000, "rating": 4.1, "review_count": None,
            "image_url": None, "variant_id": None, "source": "olx",
            "url": "https://www.olx.in/cars_c84",
        },
        {
            "id": "olx_c3", "title": "Honda City ZX CVT 2017",
            "description": "68000 km, first owner, petrol automatic, sunroof, full service history",
            "tags": ["used", "car", "sedan", "petrol", "honda", "city", "automatic", "second hand"],
            "price": 620000, "rating": 4.4, "review_count": None,
            "image_url": None, "variant_id": None, "source": "olx",
            "url": "https://www.olx.in/cars_c84",
        },
        {
            "id": "olx_c4", "title": "Tata Nexon XZ+ 2020",
            "description": "38000 km, first owner, petrol, 5-star safety, sunroof, reverse camera",
            "tags": ["used", "car", "suv", "petrol", "tata", "nexon", "second hand"],
            "price": 890000, "rating": 4.5, "review_count": None,
            "image_url": None, "variant_id": None, "source": "olx",
            "url": "https://www.olx.in/cars_c84",
        },
        {
            "id": "olx_b1", "title": "Royal Enfield Classic 350 2021",
            "description": "18000 km, first owner, single owner, well maintained, genuine colour",
            "tags": ["used", "bike", "motorcycle", "royal enfield", "classic", "cruiser", "second hand"],
            "price": 145000, "rating": 4.4, "review_count": None,
            "image_url": None, "variant_id": None, "source": "olx",
            "url": "https://www.olx.in/motorcycles_c107",
        },
        {
            "id": "olx_b2", "title": "Honda Activa 6G 2022",
            "description": "12000 km, first owner, OBD2 compliant, good mileage, scratch-free",
            "tags": ["used", "scooter", "activa", "honda", "city", "daily", "second hand"],
            "price": 65000, "rating": 4.2, "review_count": None,
            "image_url": None, "variant_id": None, "source": "olx",
            "url": "https://www.olx.in/motorcycles_c107",
        },
        {
            "id": "olx_p1", "title": "iPhone 13 128GB Midnight",
            "description": "10 months old, excellent condition, all accessories, battery 94%",
            "tags": ["used", "iphone", "smartphone", "apple", "mobile", "second hand"],
            "price": 42000, "rating": 4.5, "review_count": None,
            "image_url": None, "variant_id": None, "source": "olx",
            "url": "https://www.olx.in/mobile-phones_c339",
        },
        {
            "id": "olx_p2", "title": "Samsung Galaxy S21 5G 128GB",
            "description": "8 months old, no scratches, original box, charger included",
            "tags": ["used", "samsung", "smartphone", "android", "5g", "mobile", "second hand"],
            "price": 32000, "rating": 4.1, "review_count": None,
            "image_url": None, "variant_id": None, "source": "olx",
            "url": "https://www.olx.in/mobile-phones_c339",
        },
    ],

    # ── Amazon.in — general products ────────────────────────────────────────
    "amazon": [
        # Running shoes
        {
            "id": "amz_1", "title": "Nike Air Zoom Pegasus 40",
            "description": "Road running, Air Zoom cushioning, responsive plate, breathable mesh",
            "tags": ["running", "shoes", "road", "cushioned", "nike", "daily", "training"],
            "price": 9995, "rating": 4.5, "review_count": 14200,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=nike+running+shoes",
        },
        {
            "id": "amz_2", "title": "Skechers Go Run 7 Hyper",
            "description": "Ultra-lightweight everyday trainer, flat feet friendly, wide toe box, shock-absorbing",
            "tags": ["running", "shoes", "road", "lightweight", "flat feet", "skechers", "daily"],
            "price": 3999, "rating": 4.2, "review_count": 6700,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=skechers+running+shoes",
        },
        {
            "id": "amz_3", "title": "Puma Voyage Nitro 2 Trail",
            "description": "Trail running, Nitro foam, aggressive grip outsole, waterproof upper",
            "tags": ["running", "shoes", "trail", "grip", "puma", "waterproof", "outdoor"],
            "price": 5999, "rating": 4.3, "review_count": 4200,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=puma+trail+running+shoes",
        },
        {
            "id": "amz_4", "title": "ASICS Gel-Nimbus 25",
            "description": "Premium daily trainer, GEL cushioning, excellent arch support, flat feet",
            "tags": ["running", "shoes", "road", "cushioned", "asics", "flat feet", "arch support"],
            "price": 12999, "rating": 4.6, "review_count": 3100,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=asics+running+shoes",
        },
        # Skincare
        {
            "id": "amz_5", "title": "Neutrogena Oil-Free Moisturiser SPF 15",
            "description": "Lightweight daily moisturiser for oily skin, non-comedogenic, SPF protection",
            "tags": ["skincare", "moisturiser", "oily skin", "spf", "neutrogena", "daily", "face"],
            "price": 799, "rating": 4.5, "review_count": 31000,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=neutrogena+moisturiser",
        },
        {
            "id": "amz_6", "title": "Minimalist 10% Niacinamide Serum",
            "description": "Controls oil, reduces pores and dark spots, suitable for oily and acne-prone skin",
            "tags": ["skincare", "serum", "niacinamide", "oily skin", "acne", "minimalist", "face"],
            "price": 599, "rating": 4.4, "review_count": 48000,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=minimalist+niacinamide",
        },
        {
            "id": "amz_7", "title": "Cetaphil Moisturising Cream 250g",
            "description": "Dermatologist recommended, for dry and sensitive skin, fragrance-free, non-greasy",
            "tags": ["skincare", "moisturiser", "dry skin", "sensitive", "cetaphil", "face", "body"],
            "price": 549, "rating": 4.5, "review_count": 62000,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=cetaphil+moisturiser",
        },
        # Smartphones
        {
            "id": "amz_8", "title": "Redmi Note 13 Pro+ 5G 8/256GB",
            "description": "200MP periscope camera, 120W fast charging, AMOLED, Snapdragon 7s Gen 2",
            "tags": ["smartphone", "android", "5g", "camera", "redmi", "xiaomi", "fast charging"],
            "price": 26999, "rating": 4.4, "review_count": 18000,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=redmi+note+13+pro+plus",
        },
        {
            "id": "amz_9", "title": "Samsung Galaxy M34 5G 6/128GB",
            "description": "6000mAh battery, 50MP camera, 5G, sAMOLED display, water-resistant",
            "tags": ["smartphone", "android", "5g", "battery", "samsung", "camera"],
            "price": 15999, "rating": 4.4, "review_count": 38000,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=samsung+galaxy+m34",
        },
        # Gym / fitness
        {
            "id": "amz_10", "title": "Boldfit Resistance Bands Set (5-pack)",
            "description": "Latex loop bands, 5 resistance levels, for home workout, stretching, physiotherapy",
            "tags": ["gym", "fitness", "workout", "resistance bands", "home gym", "training"],
            "price": 499, "rating": 4.3, "review_count": 29000,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=resistance+bands",
        },
        {
            "id": "amz_11", "title": "Yatri Adjustable Dumbbell 10kg Set",
            "description": "Cast iron, rubber coating, adjustable weight, anti-roll hexagonal, home gym",
            "tags": ["gym", "fitness", "dumbbell", "weights", "home gym", "training", "strength"],
            "price": 1999, "rating": 4.2, "review_count": 11000,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=adjustable+dumbbell",
        },
        # Laptop bags / accessories
        {
            "id": "amz_12", "title": "WD 1TB My Passport Portable SSD",
            "description": "256-bit AES encryption, USB-C, 1050 MB/s, compact, password protected",
            "tags": ["storage", "ssd", "portable", "wd", "laptop", "backup", "work"],
            "price": 6999, "rating": 4.6, "review_count": 8400,
            "image_url": None, "variant_id": None, "source": "amazon",
            "url": "https://www.amazon.in/s?k=wd+portable+ssd",
        },
    ],

    # ── Flipkart — laptops, TVs, appliances, fashion ────────────────────────
    "flipkart": [
        # Laptops
        {
            "id": "fk_l1", "title": "Lenovo IdeaPad Slim 3 Ryzen 5 7520U",
            "description": "15.6\" FHD, 8GB RAM, 512GB SSD, Windows 11, Office H&S 2021, 3-cell battery",
            "tags": ["laptop", "lenovo", "ideapad", "ryzen", "student", "work", "office", "college"],
            "price": 42990, "rating": 4.3, "review_count": 22000,
            "image_url": None, "variant_id": None, "source": "flipkart",
            "url": "https://www.flipkart.com/search?q=lenovo+ideapad+slim+3",
        },
        {
            "id": "fk_l2", "title": "HP 15s Intel Core i3-1215U",
            "description": "15.6\" FHD, 8GB RAM, 512GB SSD, Intel UHD graphics, lightweight, good battery",
            "tags": ["laptop", "hp", "intel", "i3", "student", "work", "office", "daily"],
            "price": 37990, "rating": 4.2, "review_count": 31000,
            "image_url": None, "variant_id": None, "source": "flipkart",
            "url": "https://www.flipkart.com/search?q=hp+15s+laptop",
        },
        {
            "id": "fk_l3", "title": "ASUS VivoBook 15 Ryzen 5 5500U",
            "description": "15.6\" FHD, 8GB RAM, 512GB SSD, thin & light, fingerprint sensor, fast boot",
            "tags": ["laptop", "asus", "vivobook", "ryzen", "thin", "light", "student", "college"],
            "price": 44990, "rating": 4.4, "review_count": 17000,
            "image_url": None, "variant_id": None, "source": "flipkart",
            "url": "https://www.flipkart.com/search?q=asus+vivobook+15",
        },
        # Headphones / audio
        {
            "id": "fk_h1", "title": "Sony WH-1000XM5 Wireless ANC",
            "description": "Industry-best noise cancelling, 30hr battery, multipoint, LDAC, premium comfort",
            "tags": ["headphone", "wireless", "anc", "noise cancelling", "sony", "premium", "music"],
            "price": 24990, "rating": 4.7, "review_count": 8900,
            "image_url": None, "variant_id": None, "source": "flipkart",
            "url": "https://www.flipkart.com/search?q=sony+wh1000xm5",
        },
        {
            "id": "fk_h2", "title": "boAt Rockerz 550 Bluetooth Headphone",
            "description": "50hr playtime, 40mm drivers, foldable, quick charge, ASAP charging",
            "tags": ["headphone", "bluetooth", "wireless", "boat", "music", "bass", "budget"],
            "price": 1499, "rating": 4.1, "review_count": 95000,
            "image_url": None, "variant_id": None, "source": "flipkart",
            "url": "https://www.flipkart.com/search?q=boat+rockerz+550",
        },
        # TVs
        {
            "id": "fk_t1", "title": "Samsung 43\" Crystal 4K UHD Smart TV",
            "description": "Crystal Processor 4K, PurColor, HDR, Tizen OS, built-in Alexa",
            "tags": ["tv", "television", "samsung", "4k", "smart", "uhd", "43 inch", "living room"],
            "price": 32990, "rating": 4.4, "review_count": 41000,
            "image_url": None, "variant_id": None, "source": "flipkart",
            "url": "https://www.flipkart.com/search?q=samsung+43+inch+4k+tv",
        },
        {
            "id": "fk_t2", "title": "Mi 43\" X Series 4K QLED Smart TV",
            "description": "Quantum dot display, Dolby Vision, 30W speakers, Android TV, 4K upscaling",
            "tags": ["tv", "television", "xiaomi", "mi", "4k", "qled", "smart", "43 inch"],
            "price": 29999, "rating": 4.3, "review_count": 26000,
            "image_url": None, "variant_id": None, "source": "flipkart",
            "url": "https://www.flipkart.com/search?q=mi+43+inch+qled+tv",
        },
        # Appliances
        {
            "id": "fk_a1", "title": "Samsung 253L 3-Star Frost Free Refrigerator",
            "description": "Curd Maestro, Digital Inverter, Convertible 5-in-1, All-Around Cooling",
            "tags": ["refrigerator", "fridge", "samsung", "double door", "frost free", "kitchen"],
            "price": 24990, "rating": 4.4, "review_count": 19000,
            "image_url": None, "variant_id": None, "source": "flipkart",
            "url": "https://www.flipkart.com/search?q=samsung+refrigerator+double+door",
        },
    ],
}

from openai import AsyncOpenAI
from playwright.async_api import async_playwright
try:
    from playwright_stealth import stealth_async as _stealth
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False
    print("[browser_agent] playwright-stealth not installed — bot detection may trigger")

_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

_VISION_MODEL = "llama-3.2-90b-vision-preview"

# ── Search URL templates ────────────────────────────────────────────────────

_SEARCH_URLS = {
    "amazon":   "https://www.amazon.in/s?k={query}",
    "flipkart": "https://www.flipkart.com/search?q={query}",
    "carwale":  "https://www.carwale.com/new-cars/?q={query}",
    "olx":      "https://www.olx.in/items/q-{query}",
}

# ── Vision extraction prompt ────────────────────────────────────────────────

_EXTRACT_PROMPT = """You are looking at a product search results page screenshot.

Extract every visible product listing. For each one return:
- title: exact product name as shown
- price: price in INR as a plain number (e.g. 1299, not "₹1,299"). If a range, use the lower number.
- rating: star rating out of 5 as a decimal if visible (e.g. 4.3), else null
- review_count: number of ratings/reviews if visible as an integer, else null
- description: any visible highlights, specs, or tagline (1-2 sentences max)
- tags: list of relevant keywords extracted from title and description

Return ONLY a valid JSON array, nothing else:
[
  {
    "title": "...",
    "price": 1299,
    "rating": 4.3,
    "review_count": 1500,
    "description": "...",
    "tags": ["tag1", "tag2"]
  }
]

Rules:
- Skip any product where price is not visible or is 0
- Include ALL visible products, even if some fields are null
- Do not add commentary, just the JSON array
"""


# ── Site routing ─────────────────────────────────────────────────────────────
# IMPORTANT: order matters — used/second-hand check before vehicle check,
# so "used car" → OLX, not CarWale (CarWale = new cars/bikes research)

def _pick_site(intent: dict) -> str:
    combined = (
        (intent.get("category") or "") + " " +
        (intent.get("use_case") or "") + " " +
        " ".join(intent.get("constraints", []) or [])
    ).lower()

    # ── Used / second-hand first (highest priority) ──────────────────────────
    _used_kw = [
        "used", "second hand", "secondhand", "second-hand",
        "pre-owned", "preowned", "pre owned", "old ", "refurbished",
        "preloved", "pre-loved",
    ]
    if any(w in combined for w in _used_kw):
        return "olx"

    # ── Vehicles (new cars / bikes / scooters) ───────────────────────────────
    _vehicle_kw = [
        "car", "cars", "bike", "bikes", "motorcycle", "motorcycles",
        "scooter", "scooters", "suv", "sedan", "hatchback", "vehicle",
        "vehicles", "auto", "swift", "alto", "i20", "creta", "nexon",
        "fortuner", "innova", "baleno", "brezza", "sonet", "venue",
        "activa", "splendor", "pulsar", "unicorn", "classic 350",
        "royal enfield", "tvs", "bajaj", "hero honda",
        "new car", "new bike", "buy car", "buy bike",
    ]
    if any(w in combined for w in _vehicle_kw):
        return "carwale"

    # ── Flipkart — laptops, TVs, appliances, fashion ─────────────────────────
    _flipkart_kw = [
        "laptop", "laptops", "notebook",
        "television", "tv", "smart tv", "led tv",
        "refrigerator", "fridge", "washing machine", "dishwasher",
        "air conditioner", "ac ", " ac", "cooler",
        "headphone", "earphone", "earbuds",
        "fashion", "clothes", "clothing", "shirt", "jeans", "kurta",
        "dress", "saree", "ethnic", "footwear", "sandal", "heels",
        "monitor", "printer", "camera dslr",
    ]
    if any(w in combined for w in _flipkart_kw):
        return "flipkart"

    # ── Default: Amazon ───────────────────────────────────────────────────────
    return "amazon"


def _build_query(intent: dict) -> str:
    parts = [p for p in [
        intent.get("category"),
        intent.get("use_case"),
    ] if p]
    return " ".join(parts) if parts else "products"


# ── Site-specific wait selectors (what to wait for before screenshotting) ──

_WAIT_SELECTORS = {
    "amazon":   "[data-component-type='s-search-result']",   # product card
    "flipkart": "._1AtVbE",                                  # product tile
    "carwale":  ".gsc-search-result, .listing-card, [class*='car-card'], [class*='CarCard']",
    "olx":      "[data-aut-id='itemBox'], .EIR5N",           # OLX listing card
}

# ── Browser + screenshot ────────────────────────────────────────────────────

async def _get_screenshot_b64(url: str, site: str = "amazon") -> Optional[str]:
    """Launch a stealth browser, load the URL, wait for products, return screenshot."""
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",  # hides headless flag
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                extra_http_headers={
                    "Accept-Language": "en-IN,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                },
            )
            page = await context.new_page()

            # Apply stealth patches to hide Playwright's automation fingerprint
            if _STEALTH_AVAILABLE:
                await _stealth(page)

            # Remove the navigator.webdriver property that sites detect
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
                window.chrome = { runtime: {} };
            """)

            print(f"[browser_agent] navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=25000)

            # Wait for actual product cards to appear (site-specific selector)
            selector = _WAIT_SELECTORS.get(site, "")
            if selector:
                try:
                    await page.wait_for_selector(selector, timeout=8000)
                    print(f"[browser_agent] product cards loaded on {site}")
                except Exception:
                    # Selector didn't appear — still try screenshot
                    print(f"[browser_agent] selector timeout on {site}, taking screenshot anyway")
                    await page.wait_for_timeout(3000)
            else:
                await page.wait_for_timeout(3000)

            # Scroll to trigger lazy-loaded cards
            await page.evaluate("window.scrollBy(0, 500)")
            await page.wait_for_timeout(800)

            screenshot_bytes = await page.screenshot(type="jpeg", quality=80, full_page=False)
            await browser.close()

        b64 = base64.b64encode(screenshot_bytes).decode()
        print(f"[browser_agent] screenshot captured ({len(b64)//1024}KB)")
        return b64

    except Exception as exc:
        print(f"[browser_agent] screenshot error: {exc}")
        return None


# ── Vision extraction ───────────────────────────────────────────────────────

async def _vision_extract(screenshot_b64: str, site: str) -> list[dict]:
    """Send screenshot to Groq Vision and parse product list."""
    try:
        response = await _client.chat.completions.create(
            model=_VISION_MODEL,
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{screenshot_b64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": _EXTRACT_PROMPT,
                        },
                    ],
                }
            ],
        )
        raw = response.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            print(f"[browser_agent] vision returned no JSON array")
            return []

        items = json.loads(match.group())
        products = []
        for i, item in enumerate(items):
            price = float(item.get("price") or 0)
            if price <= 0:
                continue
            products.append({
                "id": f"{site}_{i}",
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "tags": list(item.get("tags") or []) + [site],
                "price": price,
                "rating": item.get("rating"),
                "review_count": item.get("review_count"),
                "image_url": None,
                "variant_id": None,
                "source": site,
            })
        return products

    except Exception as exc:
        print(f"[browser_agent] vision extraction error: {exc}")
        return []


# ── Public API ──────────────────────────────────────────────────────────────

def _status(text: str) -> dict:
    return {"type": "status", "text": text}


async def search_products_stream(intent: dict, limit: int = 15):
    """
    Async generator — yields status dicts then a final products dict.
    Use in main.py to stream live status to the frontend.
    """
    site = _pick_site(intent)
    query = _build_query(intent)
    site_labels = {"amazon": "Amazon.in", "flipkart": "Flipkart", "carwale": "CarWale", "olx": "OLX.in"}
    label = site_labels.get(site, site)
    url = _SEARCH_URLS[site].format(query=query.replace(" ", "+"))

    yield _status(f"Opening {label}…")
    screenshot_b64 = await _get_screenshot_b64(url, site)

    products = []

    if screenshot_b64:
        yield _status(f"Screenshot taken — reading with AI vision…")
        products = await _vision_extract(screenshot_b64, site)

    # Fallback to demo data if live browsing failed or returned nothing
    if not products:
        yield _status(f"Using curated listings for {label}…")
        products = _get_demo_products(site, intent)

    budget_max = intent.get("budget_max")
    if budget_max:
        products = [p for p in products if p["price"] <= budget_max]

    count = len(products)
    yield _status(f"Found {count} product{'s' if count != 1 else ''} — ranking by confidence…")
    yield {"type": "products", "data": products[:limit]}


async def search_products_broad_stream(intent: dict):
    """Broad fallback — also yields status events."""
    site = _pick_site(intent)
    site_labels = {"amazon": "Amazon.in", "flipkart": "Flipkart", "carwale": "CarWale", "olx": "OLX.in"}

    # Fallback site logic
    fallback_map = {"amazon": "flipkart", "flipkart": "amazon", "carwale": "olx", "olx": "carwale"}
    fallback_site = fallback_map.get(site, "amazon")

    loose_intent = {"category": intent.get("category", "")}
    products = []

    async for event in search_products_stream(loose_intent, limit=10):
        if event["type"] == "products":
            products = event["data"]
        else:
            yield event

    if not products:
        label = site_labels.get(fallback_site, fallback_site)
        yield _status(f"Trying {label} instead…")
        query = _build_query(loose_intent)
        url = _SEARCH_URLS[fallback_site].format(query=query.replace(" ", "+"))
        screenshot_b64 = await _get_screenshot_b64(url, fallback_site)
        if screenshot_b64:
            products = await _vision_extract(screenshot_b64, fallback_site)
        if not products:
            products = _get_demo_products(fallback_site, intent)

    yield {"type": "products", "data": products}


def _get_demo_products(site: str, intent: dict) -> list[dict]:
    """Return curated demo products filtered loosely by intent when live browsing fails."""
    pool = list(_DEMO_PRODUCTS.get(site, _DEMO_PRODUCTS["amazon"]))

    category = (intent.get("category") or "").lower()
    use_case = (intent.get("use_case") or "").lower()
    constraints_text = " ".join(intent.get("constraints") or []).lower()
    intent_text = category + " " + use_case + " " + constraints_text

    # ── Hard type filter — prevent cross-category pollution ─────────────────
    # e.g. never return a scooter when the user asked for a car
    _car_words   = {"car", "cars", "sedan", "suv", "hatchback", "vehicle"}
    _bike_words  = {"bike", "bikes", "motorcycle", "scooter", "activa", "splendor", "pulsar"}
    _phone_words = {"phone", "smartphone", "mobile", "iphone", "samsung"}

    wants_car   = any(w in intent_text for w in _car_words)
    wants_bike  = any(w in intent_text for w in _bike_words)
    wants_phone = any(w in intent_text for w in _phone_words)

    def _is_car(p):   return any(t in p["tags"] for t in ["car", "sedan", "suv", "hatchback"])
    def _is_bike(p):  return any(t in p["tags"] for t in ["bike", "motorcycle", "scooter", "activa"])
    def _is_phone(p): return any(t in p["tags"] for t in ["iphone", "smartphone", "samsung", "mobile"])

    if wants_car and not wants_bike:
        pool = [p for p in pool if not _is_bike(p) and not _is_phone(p)]
    elif wants_bike and not wants_car:
        pool = [p for p in pool if not _is_car(p) and not _is_phone(p)]
    elif wants_phone:
        pool = [p for p in pool if not _is_car(p) and not _is_bike(p)]

    # If hard filter wiped everything, go back to full pool (better than empty)
    if not pool:
        pool = list(_DEMO_PRODUCTS.get(site, _DEMO_PRODUCTS["amazon"]))

    # ── Keyword score — rank remaining products by relevance ─────────────────
    keywords = [w for w in intent_text.split() if len(w) > 2]

    if keywords:
        scored = []
        for p in pool:
            text = (p["title"] + " " + p.get("description", "") + " " + " ".join(p["tags"])).lower()
            hits = sum(1 for k in keywords if k in text)
            scored.append((hits, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        # Only use filtered list if at least one product matched at least 1 keyword
        filtered = [p for hits, p in scored if hits > 0]
        pool = filtered if filtered else pool

    return pool


async def create_cart(variant_id: str, quantity: int = 1) -> Optional[str]:
    """Not applicable for browser-sourced products."""
    return None
