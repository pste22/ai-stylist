#!/usr/bin/env python3
"""Automated catalog expansion — grows affiliate_products.json to 200+ products.

Strategy:
  1. Gemini Flash generates batches of product metadata per category.
  2. For each product, we search Amazon and extract the top result's
     ASIN + image URL (same urllib technique used for image fixes).
  3. Merge with existing products (skip duplicates by name).
  4. Write to data/affiliate_products.json ready for migrate_products.py.

Usage (from prototype/):
    python expand_catalog.py            # full run (~200 products)
    python expand_catalog.py --dry-run  # generate + print, no file write
    python expand_catalog.py --target 300

Env: GEMINI_API_KEY  (already in prototype/.env)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DATA_FILE = Path(__file__).parent / "data" / "affiliate_products.json"
AFFILIATE_TAG = "mira0f-20"

# ── Category blueprint ────────────────────────────────────────────────────────
# Each entry: (category_id, gender, search_seed_list, target_count)
CATEGORIES: list[tuple[str, str, list[str], int]] = [
    ("dresses",    "women", [
        "women midi dress casual", "women wrap dress floral", "women maxi dress summer",
        "women bodycon dress night out", "women shirt dress work", "women mini skirt dress",
        "women sundress boho", "women cocktail dress elegant",
    ], 30),
    ("tops",       "women", [
        "women blouse work casual", "women crop top trendy", "women linen shirt summer",
        "women off shoulder top", "women ribbed tank top", "women satin blouse office",
        "women graphic tee casual", "women cami top layering",
    ], 30),
    ("bottoms",    "women", [
        "women high waist jeans", "women wide leg trousers", "women midi skirt elegant",
        "women linen shorts summer", "women cargo pants trendy", "women pleated skirt work",
        "women paperbag waist pants", "women bermuda shorts",
    ], 25),
    ("outerwear",  "women", [
        "women trench coat classic", "women blazer work", "women leather jacket moto",
        "women puffer jacket winter", "women longline cardigan", "women denim jacket casual",
        "women wool coat winter", "women utility jacket trendy",
    ], 25),
    ("shoes",      "women", [
        "women block heel sandals", "women white sneakers casual", "women ankle boots work",
        "women loafers slip on", "women pointed toe heels", "women platform sneakers",
        "women mules slip on summer", "women chelsea boots fall",
    ], 25),
    ("bags",       "women", [
        "women canvas tote bag", "women leather crossbody bag", "women mini shoulder bag",
        "women work tote structured", "women bucket bag trendy", "women clutch evening",
        "women backpack fashion", "women belt bag fanny pack",
    ], 20),
    ("accessories","women", [
        "women gold hoop earrings", "women silk scarf", "women straw hat summer",
        "women belt leather minimalist", "women layering necklace gold",
        "women sunglasses oversized", "women hair clips claw", "women watch minimalist",
    ], 20),
    ("activewear", "women", [
        "women yoga leggings high waist", "women sports bra medium support",
        "women running shorts", "women athletic set matching", "women gym hoodie",
    ], 15),
    ("men_tops",   "men", [
        "men linen shirt summer casual", "men polo shirt", "men graphic tee streetwear",
        "men oxford shirt work", "men henley shirt", "men crewneck sweatshirt",
    ], 15),
    ("men_bottoms","men", [
        "men slim chino pants", "men cargo shorts", "men jogger pants",
        "men straight fit jeans", "men linen trousers summer",
    ], 15),
]

STYLE_MAP = {
    "dresses":    ["casual", "chic", "feminine", "elegant", "everyday"],
    "tops":       ["casual", "everyday", "versatile", "minimal"],
    "bottoms":    ["casual", "work", "everyday", "chic"],
    "outerwear":  ["classic", "layering", "work", "weekend"],
    "shoes":      ["everyday", "versatile", "casual", "chic"],
    "bags":       ["everyday", "work", "chic", "functional"],
    "accessories":["minimal", "classic", "everyday", "statement"],
    "activewear": ["sporty", "athletic", "functional", "comfort"],
    "men_tops":   ["casual", "classic", "everyday", "versatile"],
    "men_bottoms":["casual", "classic", "work", "everyday"],
}

COLORS = [
    "black", "white", "navy", "beige", "cream", "camel", "sage", "rust",
    "burgundy", "olive", "forest green", "dusty pink", "lavender", "tan",
    "charcoal", "sand", "terracotta", "cobalt blue", "off-white", "khaki",
]


# ── Gemini batch generation ───────────────────────────────────────────────────
PRODUCT_BLUEPRINTS: dict[str, list[dict]] = {
    "dresses": [
        {"name": "Women's Floral Wrap Midi Dress",         "color": "dusty pink",   "price": 42.99, "style_tags": ["casual", "feminine", "boho"]},
        {"name": "Women's Sleeveless Bodycon Mini Dress",   "color": "black",        "price": 34.99, "style_tags": ["trendy", "night out", "chic"]},
        {"name": "Women's Linen Shirt Dress Pockets",       "color": "beige",        "price": 49.99, "style_tags": ["casual", "everyday", "minimal"]},
        {"name": "Women's Ruffle Hem Maxi Dress",           "color": "white",        "price": 55.99, "style_tags": ["boho", "feminine", "weekend"]},
        {"name": "Women's V Neck Satin Slip Dress",         "color": "navy",         "price": 38.99, "style_tags": ["chic", "elegant", "night out"]},
        {"name": "Women's Tiered Smocked Sundress",         "color": "terracotta",   "price": 36.99, "style_tags": ["boho", "casual", "summer"]},
        {"name": "Women's Belted Trench Shirt Dress",       "color": "camel",        "price": 68.99, "style_tags": ["work", "classic", "chic"]},
        {"name": "Women's Ribbed Knit Midi Dress",          "color": "cream",        "price": 44.99, "style_tags": ["minimal", "casual", "everyday"]},
        {"name": "Women's Floral Print Wrap Maxi Dress",    "color": "sage",         "price": 52.99, "style_tags": ["boho", "feminine", "weekend"]},
        {"name": "Women's Mesh Long Sleeve Mini Dress",     "color": "black",        "price": 39.99, "style_tags": ["trendy", "night out", "statement"]},
        {"name": "Women's Lace Trim Slip Midi Dress",       "color": "dusty pink",   "price": 47.99, "style_tags": ["feminine", "romantic", "chic"]},
        {"name": "Women's Denim Button Front Midi Dress",   "color": "navy",         "price": 58.99, "style_tags": ["casual", "classic", "weekend"]},
        {"name": "Women's Smocked Waist Floral Dress",      "color": "lavender",     "price": 41.99, "style_tags": ["boho", "feminine", "casual"]},
        {"name": "Women's Long Sleeve Turtleneck Dress",    "color": "charcoal",     "price": 46.99, "style_tags": ["minimal", "classic", "work"]},
        {"name": "Women's Off Shoulder Ruched Dress",       "color": "burgundy",     "price": 43.99, "style_tags": ["feminine", "night out", "chic"]},
        {"name": "Women's Pleated Chiffon Maxi Dress",      "color": "sage",         "price": 62.99, "style_tags": ["elegant", "feminine", "occasions"]},
        {"name": "Women's Square Neck Puff Sleeve Dress",   "color": "white",        "price": 39.99, "style_tags": ["trendy", "feminine", "casual"]},
        {"name": "Women's Flowy Bohemian Maxi Dress",       "color": "tan",          "price": 54.99, "style_tags": ["boho", "weekend", "casual"]},
        {"name": "Women's Halter Neck Backless Dress",      "color": "black",        "price": 45.99, "style_tags": ["night out", "statement", "chic"]},
        {"name": "Women's Jacquard Midi Pencil Dress",      "color": "navy",         "price": 72.99, "style_tags": ["work", "classic", "elegant"]},
    ],
    "tops": [
        {"name": "Women's Oversized Linen Button Shirt",    "color": "white",        "price": 37.99, "style_tags": ["casual", "minimal", "everyday"]},
        {"name": "Women's Cropped Ribbed Tank Top",         "color": "black",        "price": 22.99, "style_tags": ["trendy", "casual", "everyday"]},
        {"name": "Women's Satin Blouse Bow Neck",           "color": "cream",        "price": 44.99, "style_tags": ["work", "chic", "elegant"]},
        {"name": "Women's Off Shoulder Ruffle Blouse",      "color": "white",        "price": 32.99, "style_tags": ["feminine", "casual", "weekend"]},
        {"name": "Women's Striped Breton Long Sleeve Top",  "color": "navy",         "price": 28.99, "style_tags": ["classic", "casual", "everyday"]},
        {"name": "Women's Floral Chiffon Wrap Blouse",      "color": "dusty pink",   "price": 38.99, "style_tags": ["feminine", "work", "chic"]},
        {"name": "Women's Cropped Knit Cardigan",           "color": "cream",        "price": 49.99, "style_tags": ["casual", "layering", "weekend"]},
        {"name": "Women's Smocked Puff Sleeve Blouse",      "color": "sage",         "price": 34.99, "style_tags": ["trendy", "feminine", "boho"]},
        {"name": "Women's Basic V Neck Tee 3 Pack",         "color": "white",        "price": 29.99, "style_tags": ["casual", "minimal", "everyday"]},
        {"name": "Women's Silk Effect Cami Top",            "color": "black",        "price": 26.99, "style_tags": ["chic", "casual", "layering"]},
        {"name": "Women's Lace Up Front Corset Top",        "color": "burgundy",     "price": 31.99, "style_tags": ["trendy", "statement", "night out"]},
        {"name": "Women's Linen Henley Button Top",         "color": "beige",        "price": 33.99, "style_tags": ["casual", "minimal", "weekend"]},
        {"name": "Women's Sheer Long Sleeve Blouse",        "color": "white",        "price": 35.99, "style_tags": ["work", "layering", "chic"]},
        {"name": "Women's Boxy Crop Graphic Tee",           "color": "charcoal",     "price": 24.99, "style_tags": ["casual", "trendy", "everyday"]},
        {"name": "Women's Cold Shoulder Knit Sweater",      "color": "camel",        "price": 54.99, "style_tags": ["classic", "casual", "weekend"]},
        {"name": "Women's Tied Front Gingham Shirt",        "color": "navy",         "price": 36.99, "style_tags": ["classic", "casual", "weekend"]},
        {"name": "Women's Strapless Bandeau Tube Top",      "color": "black",        "price": 18.99, "style_tags": ["trendy", "casual", "summer"]},
        {"name": "Women's Merino Wool Fitted Turtleneck",   "color": "cream",        "price": 68.99, "style_tags": ["classic", "work", "minimal"]},
    ],
    "bottoms": [
        {"name": "Women's High Rise Straight Leg Jeans",    "color": "navy",         "price": 54.99, "style_tags": ["classic", "casual", "everyday"]},
        {"name": "Women's Wide Leg Linen Trousers",         "color": "beige",        "price": 47.99, "style_tags": ["casual", "minimal", "chic"]},
        {"name": "Women's Pleated Midi Skirt Elastic Waist","color": "black",        "price": 38.99, "style_tags": ["work", "classic", "chic"]},
        {"name": "Women's Biker Shorts High Waist",         "color": "black",        "price": 24.99, "style_tags": ["sporty", "casual", "comfort"]},
        {"name": "Women's Cargo Wide Leg Pants",            "color": "olive",        "price": 52.99, "style_tags": ["trendy", "casual", "weekend"]},
        {"name": "Women's Flowy Palazzo Pants",             "color": "cream",        "price": 43.99, "style_tags": ["boho", "casual", "chic"]},
        {"name": "Women's Denim Mini Skirt Frayed Hem",     "color": "navy",         "price": 34.99, "style_tags": ["casual", "trendy", "weekend"]},
        {"name": "Women's High Waist Tailored Trousers",    "color": "charcoal",     "price": 59.99, "style_tags": ["work", "classic", "elegant"]},
        {"name": "Women's Floral Wrap Midi Skirt",          "color": "terracotta",   "price": 41.99, "style_tags": ["boho", "feminine", "weekend"]},
        {"name": "Women's Satin Bias Cut Midi Skirt",       "color": "dusty pink",   "price": 46.99, "style_tags": ["chic", "elegant", "night out"]},
        {"name": "Women's Paperbag Waist Bermuda Shorts",   "color": "khaki",        "price": 36.99, "style_tags": ["casual", "weekend", "classic"]},
        {"name": "Women's Slim Fit Cigarette Trousers",     "color": "black",        "price": 55.99, "style_tags": ["work", "minimal", "chic"]},
        {"name": "Women's Distressed Boyfriend Jeans",      "color": "navy",         "price": 49.99, "style_tags": ["casual", "classic", "weekend"]},
        {"name": "Women's Faux Leather Mini Skirt",         "color": "black",        "price": 38.99, "style_tags": ["trendy", "night out", "statement"]},
    ],
    "outerwear": [
        {"name": "Women's Classic Belted Trench Coat",      "color": "camel",        "price": 119.99,"style_tags": ["classic", "work", "chic"]},
        {"name": "Women's Oversized Wool Blend Coat",       "color": "charcoal",     "price": 139.99,"style_tags": ["classic", "elegant", "winter"]},
        {"name": "Women's Cropped Faux Leather Jacket",     "color": "black",        "price": 69.99, "style_tags": ["trendy", "casual", "statement"]},
        {"name": "Women's Longline Puffer Jacket Quilted",  "color": "navy",         "price": 89.99, "style_tags": ["casual", "winter", "comfort"]},
        {"name": "Women's Open Front Longline Cardigan",    "color": "cream",        "price": 62.99, "style_tags": ["casual", "layering", "weekend"]},
        {"name": "Women's Tailored Double Breasted Blazer", "color": "black",        "price": 84.99, "style_tags": ["work", "classic", "chic"]},
        {"name": "Women's Sherpa Lined Denim Jacket",       "color": "navy",         "price": 74.99, "style_tags": ["casual", "weekend", "classic"]},
        {"name": "Women's Velvet Blazer Relaxed Fit",       "color": "burgundy",     "price": 79.99, "style_tags": ["statement", "chic", "evening"]},
        {"name": "Women's Teddy Bear Fleece Jacket",        "color": "cream",        "price": 67.99, "style_tags": ["casual", "comfort", "weekend"]},
        {"name": "Women's Utility Lightweight Anorak",      "color": "olive",        "price": 72.99, "style_tags": ["casual", "outdoor", "weekend"]},
        {"name": "Women's Plaid Wool Blend Cape Coat",      "color": "charcoal",     "price": 109.99,"style_tags": ["classic", "elegant", "statement"]},
        {"name": "Women's Cropped Puffer Vest Quilted",     "color": "navy",         "price": 54.99, "style_tags": ["casual", "layering", "weekend"]},
        {"name": "Women's Faux Fur Collar Wrap Coat",       "color": "camel",        "price": 129.99,"style_tags": ["elegant", "classic", "winter"]},
    ],
    "shoes": [
        {"name": "Women's Platform White Leather Sneakers", "color": "white",        "price": 64.99, "style_tags": ["casual", "trendy", "everyday"]},
        {"name": "Women's Block Heel Mule Sandals",         "color": "tan",          "price": 48.99, "style_tags": ["chic", "casual", "summer"]},
        {"name": "Women's Chelsea Ankle Boots Leather",     "color": "black",        "price": 84.99, "style_tags": ["classic", "work", "everyday"]},
        {"name": "Women's Strappy Heeled Sandals",          "color": "nude",         "price": 54.99, "style_tags": ["elegant", "occasions", "chic"]},
        {"name": "Women's Pointed Toe Kitten Heel Pumps",   "color": "black",        "price": 69.99, "style_tags": ["work", "classic", "elegant"]},
        {"name": "Women's Slip On Loafers Penny",           "color": "camel",        "price": 58.99, "style_tags": ["classic", "casual", "everyday"]},
        {"name": "Women's Chunky Platform Sandals",         "color": "black",        "price": 52.99, "style_tags": ["trendy", "statement", "casual"]},
        {"name": "Women's Over The Knee Heeled Boots",      "color": "black",        "price": 94.99, "style_tags": ["statement", "chic", "winter"]},
        {"name": "Women's Canvas Slip On Espadrilles",      "color": "beige",        "price": 36.99, "style_tags": ["casual", "summer", "boho"]},
        {"name": "Women's Lace Up Ankle Boots Block Heel",  "color": "tan",          "price": 76.99, "style_tags": ["casual", "classic", "weekend"]},
        {"name": "Women's Barely There Heeled Sandals",     "color": "nude",         "price": 44.99, "style_tags": ["elegant", "minimal", "occasions"]},
        {"name": "Women's Flatform Sole Sneakers",          "color": "white",        "price": 58.99, "style_tags": ["trendy", "casual", "comfort"]},
    ],
    "bags": [
        {"name": "Women's Large Canvas Tote Work Bag",      "color": "beige",        "price": 38.99, "style_tags": ["casual", "work", "everyday"]},
        {"name": "Women's Leather Crossbody Bag Minimal",   "color": "tan",          "price": 64.99, "style_tags": ["minimal", "chic", "everyday"]},
        {"name": "Women's Mini Shoulder Bag Chain Strap",   "color": "black",        "price": 42.99, "style_tags": ["chic", "night out", "trendy"]},
        {"name": "Women's Woven Straw Raffia Tote Bag",     "color": "beige",        "price": 34.99, "style_tags": ["boho", "summer", "casual"]},
        {"name": "Women's Structured Top Handle Handbag",   "color": "camel",        "price": 79.99, "style_tags": ["work", "classic", "elegant"]},
        {"name": "Women's Bucket Bag Drawstring Closure",   "color": "black",        "price": 52.99, "style_tags": ["trendy", "casual", "chic"]},
        {"name": "Women's Quilted Camera Bag Crossbody",    "color": "navy",         "price": 58.99, "style_tags": ["classic", "casual", "chic"]},
        {"name": "Women's Leather Belt Bag Waist Pack",     "color": "black",        "price": 44.99, "style_tags": ["casual", "trendy", "functional"]},
        {"name": "Women's Hobo Shoulder Bag Soft Leather",  "color": "tan",          "price": 72.99, "style_tags": ["classic", "casual", "everyday"]},
        {"name": "Women's Transparent PVC Tote Bag",        "color": "cream",        "price": 32.99, "style_tags": ["trendy", "summer", "casual"]},
        {"name": "Women's Backpack Mini Fashion",           "color": "black",        "price": 48.99, "style_tags": ["casual", "everyday", "functional"]},
        {"name": "Women's Evening Clutch Bag Rhinestone",   "color": "black",        "price": 28.99, "style_tags": ["elegant", "night out", "occasions"]},
    ],
    "accessories": [
        {"name": "Women's Gold Chunky Chain Necklace",      "color": "tan",          "price": 22.99, "style_tags": ["statement", "chic", "trendy"]},
        {"name": "Women's Silk Square Scarf Twill",         "color": "dusty pink",   "price": 28.99, "style_tags": ["classic", "chic", "versatile"]},
        {"name": "Women's Wide Brim Straw Sun Hat",         "color": "beige",        "price": 24.99, "style_tags": ["boho", "summer", "casual"]},
        {"name": "Women's Oversized Square Sunglasses",     "color": "black",        "price": 18.99, "style_tags": ["trendy", "chic", "summer"]},
        {"name": "Women's Gold Hoop Earrings Large",        "color": "tan",          "price": 16.99, "style_tags": ["classic", "casual", "everyday"]},
        {"name": "Women's Leather Slim Belt Classic",       "color": "black",        "price": 26.99, "style_tags": ["classic", "work", "everyday"]},
        {"name": "Women's Layered Delicate Gold Necklace",  "color": "tan",          "price": 19.99, "style_tags": ["minimal", "classic", "everyday"]},
        {"name": "Women's Claw Hair Clip Set 4 Piece",      "color": "beige",        "price": 12.99, "style_tags": ["casual", "everyday", "trendy"]},
        {"name": "Women's Leopard Print Scarf Wrap",        "color": "tan",          "price": 23.99, "style_tags": ["classic", "statement", "chic"]},
        {"name": "Women's Minimalist Watch Mesh Band",      "color": "charcoal",     "price": 45.99, "style_tags": ["minimal", "classic", "work"]},
        {"name": "Women's Beaded Layering Bracelet Set",    "color": "dusty pink",   "price": 14.99, "style_tags": ["boho", "casual", "feminine"]},
        {"name": "Women's Structured Headband Wide",        "color": "black",        "price": 11.99, "style_tags": ["casual", "minimal", "everyday"]},
    ],
    "activewear": [
        {"name": "Women's High Waist Seamless Leggings",    "color": "black",        "price": 38.99, "style_tags": ["sporty", "comfort", "everyday"]},
        {"name": "Women's Sports Bra Medium Support",       "color": "sage",         "price": 28.99, "style_tags": ["sporty", "athletic", "comfort"]},
        {"name": "Women's Matching Bike Short Set",         "color": "charcoal",     "price": 52.99, "style_tags": ["sporty", "trendy", "athletic"]},
        {"name": "Women's Oversized Gym Hoodie",            "color": "cream",        "price": 44.99, "style_tags": ["casual", "comfort", "sporty"]},
        {"name": "Women's Athletic Running Shorts 3 Inch",  "color": "black",        "price": 26.99, "style_tags": ["sporty", "athletic", "functional"]},
        {"name": "Women's Zip Up Cropped Workout Jacket",   "color": "navy",         "price": 48.99, "style_tags": ["sporty", "athletic", "layering"]},
        {"name": "Women's Flare Yoga Pants High Rise",      "color": "olive",        "price": 42.99, "style_tags": ["sporty", "comfort", "casual"]},
        {"name": "Women's Seamless Workout Set Ribbed",     "color": "dusty pink",   "price": 56.99, "style_tags": ["sporty", "trendy", "athletic"]},
    ],
    "men_tops": [
        {"name": "Men's Linen Short Sleeve Shirt",          "color": "beige",        "price": 38.99, "style_tags": ["casual", "classic", "summer"]},
        {"name": "Men's Classic Polo Shirt",                "color": "navy",         "price": 34.99, "style_tags": ["classic", "casual", "work"]},
        {"name": "Men's Oversized Graphic Tee",             "color": "charcoal",     "price": 24.99, "style_tags": ["casual", "trendy", "everyday"]},
        {"name": "Men's Oxford Button Down Shirt",          "color": "white",        "price": 44.99, "style_tags": ["work", "classic", "chic"]},
        {"name": "Men's Henley Long Sleeve Top",            "color": "cream",        "price": 32.99, "style_tags": ["casual", "classic", "weekend"]},
        {"name": "Men's Crewneck Fleece Sweatshirt",        "color": "charcoal",     "price": 48.99, "style_tags": ["casual", "comfort", "everyday"]},
        {"name": "Men's Striped Resort Shirt",              "color": "navy",         "price": 36.99, "style_tags": ["casual", "classic", "summer"]},
        {"name": "Men's Quarter Zip Pullover Sweater",      "color": "camel",        "price": 54.99, "style_tags": ["classic", "work", "weekend"]},
        {"name": "Men's Slim Fit Dress Shirt",              "color": "white",        "price": 42.99, "style_tags": ["work", "classic", "elegant"]},
        {"name": "Men's Cotton Crew Neck T-Shirt",          "color": "black",        "price": 18.99, "style_tags": ["casual", "minimal", "everyday"]},
    ],
    "men_bottoms": [
        {"name": "Men's Slim Chino Pants",                  "color": "khaki",        "price": 48.99, "style_tags": ["work", "classic", "casual"]},
        {"name": "Men's Cargo Shorts Multi Pocket",         "color": "olive",        "price": 36.99, "style_tags": ["casual", "outdoor", "weekend"]},
        {"name": "Men's Jogger Pants Tapered",              "color": "charcoal",     "price": 42.99, "style_tags": ["casual", "comfort", "sporty"]},
        {"name": "Men's Straight Fit Classic Jeans",        "color": "navy",         "price": 54.99, "style_tags": ["classic", "casual", "everyday"]},
        {"name": "Men's Linen Drawstring Trousers",         "color": "beige",        "price": 44.99, "style_tags": ["casual", "summer", "minimal"]},
        {"name": "Men's Dress Trousers Slim Fit",           "color": "charcoal",     "price": 62.99, "style_tags": ["work", "classic", "elegant"]},
        {"name": "Men's Swim Trunks Quick Dry",             "color": "navy",         "price": 28.99, "style_tags": ["casual", "summer", "sporty"]},
        {"name": "Men's Wool Blend Dress Pants",            "color": "black",        "price": 72.99, "style_tags": ["work", "classic", "elegant"]},
    ],
}


def _gemini_generate_products(category: str, gender: str, seeds: list[str], count: int) -> list[dict]:
    """Return blueprint products for category, falling back to Gemini if available."""
    # Use hardcoded blueprints first (no API needed, no rate limits)
    blueprints = PRODUCT_BLUEPRINTS.get(category, [])
    if blueprints:
        return blueprints[:count]

    # Fallback: try Gemini if available
    try:
        from google import genai  # type: ignore
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
        prompt = f"""Generate {count} distinct fashion product entries for the "{category}" category.
Return ONLY a JSON array where each object has: name, color, price (float), style_tags (array of 2-3 strings).
Colors must be from: {', '.join(COLORS)}. No markdown."""
        resp = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        text = re.sub(r"^```(?:json)?\s*", "", resp.text.strip())
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except Exception:
        return []


# ── Image + affiliate URL generation ─────────────────────────────────────────
# Amazon blocks datacenter IPs; use Unsplash for product images.
# Affiliate links point to Amazon search — still earns commission on purchase.

# Curated Unsplash photo IDs per category for consistent, quality images
_UNSPLASH_POOL: dict[str, list[str]] = {
    "dresses":    ["KMn4VEeEPR8","BmWWRRFZLHI","rDLBArZUl1c","LrlyZzX6Sc0","lxSKpAHJV4g",
                   "vYcH7pI6v1Q","RqAMQEzIp8k","l0oM5JmBMiI","EB2T2XKOHKQ","nMffL1zjbw4"],
    "tops":       ["IF9TK5Uy-KI","J7rRzjSi5hM","fS3tGOkp0xo","fJTqyZMkLDo","mEZ3PoFGs48",
                   "9QTQFihyles","VT4CG5smzSM","omNfIqhJkE4","aO_jMXTduUE","jBnCGiMDl9I"],
    "bottoms":    ["2JIvboGLeho","CrEFkn2PsPk","3XYPaYbxBKQ","oBn8yMSA13I","hkFxFwPFAAM",
                   "8sxM7XPVS68","mSHan7dYkzM","H1PNLHAnS0s","HJckKnwCXxQ","q0YnJR0bBMc"],
    "outerwear":  ["YmQ0-nmv3_0","c9FQyqIECds","NpTPCHWFlhA","w_9GB-DFXAM","f5pHBPiPpMk",
                   "1fZC2rYkqf8","kSoG8BRDiDE","q9r3WT7VJZQ","9vph-R8LjPs","xfU7Fz-eFgk"],
    "shoes":      ["E7RLgUjjazc","h0Vxgz5tyXA","5MSSTnpLBZE","3TNsHTEWpIY","VJ2s9RdODWI",
                   "0riO7oOG--Q","6EPeH_zTsiQ","w7a7iPOjM-0","xq90jBFMoRY","a_MjLqTsOcY"],
    "bags":       ["Rg3_bdOBBX0","eHlVZcO_LOs","v3pTGwpBz8M","kAeYxE4RSPY","6-53cHoGUbs",
                   "ILip77SbmOE","CIuakYIjadc","uv5_bsypFUM","q60NOwNjPiI","_0DeltaRoPI"],
    "accessories":["tVkdGtEe17s","HjBOmBPbi9k","GrFvF78PiIU","Q9y4wv5ZICM","pMW4jzELQCw",
                   "y5hQCIn1c6o","JsVox6a4TKM","_vmMNFXt8Vk","cYyqhdbJ9TI","7e2pe9wjL9M"],
    "activewear": ["oLthDWAG244","3GZi5G5apXA","ULHxWq8reao","ASKeuOZqhYU","4wDHmSMoD_M",
                   "fOGZB_-lDSk","pmvIiOdMCsw","FdPT0GDaJM0","J-n7jHCELqQ","7kEpUPB8vNk"],
    "men_tops":   ["7YVZYZeITc8","ViEBSoZH6M4","6VPEOdpFNAs","pAtA8xe_iVM","4e2O0Sj8aEM",
                   "SYofHBgDkVQ","DgHRmCZxBjI","rK7gDmbE_bg","KIPqITwTkak","RZDKg5SJZVM"],
    "men_bottoms":["3TNsHTEWpIY","NL_UtVtOoEA","1K8hVQSAfbc","mEZ3PoFGs48","eECnLHCMBnA",
                   "fJTqyZMkLDo","VgbRMkMBp6s","qWfyGJ-T_9Y","JRs7wSRBSLo","sKr8IOgw-BU"],
}

_photo_counters: dict[str, int] = {}


def _unsplash_image(category: str, product_name: str) -> str:
    """Return a stable Unsplash image URL for the product."""
    pool = _UNSPLASH_POOL.get(category)
    if pool:
        idx = _photo_counters.get(category, 0)
        photo_id = pool[idx % len(pool)]
        _photo_counters[category] = idx + 1
        return f"https://images.unsplash.com/photo-{photo_id}?w=500&q=80&fit=crop&auto=format"
    # Generic fallback by keyword
    kw = urllib.parse.quote_plus(product_name.split()[-1])
    return f"https://source.unsplash.com/500x625/?{kw},fashion"


def _affiliate_url(name: str) -> str:
    q = urllib.parse.quote_plus(name)
    return f"https://www.amazon.com/s?k={q}&tag={AFFILIATE_TAG}"


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target", type=int, default=200)
    args = parser.parse_args()

    # Load existing products
    existing: list[dict] = []
    if DATA_FILE.exists():
        with DATA_FILE.open() as f:
            existing = [p for p in json.load(f) if not p.get("_comment")]
    existing_names = {p["name"].lower() for p in existing}
    print(f"Existing catalog: {len(existing)} products")

    new_products: list[dict] = []
    total_needed = max(0, args.target - len(existing))
    print(f"Generating ~{total_needed} new products to reach {args.target} total\n")

    for cat_id, gender, seeds, cat_count in CATEGORIES:
        if len(new_products) >= total_needed:
            break

        batch_size = min(cat_count, total_needed - len(new_products))
        print(f"── {cat_id} ({gender}) — requesting {batch_size} products from Gemini…")
        raw = _gemini_generate_products(cat_id, gender, seeds, batch_size)
        print(f"   Gemini returned {len(raw)} products")

        for item in raw:
            name = item.get("name", "").strip()
            if not name or name.lower() in existing_names:
                continue

            # Generate a deterministic pseudo-ASIN
            product_id = "GEN" + hex(abs(hash(name)))[2:10].upper()
            image_url  = _unsplash_image(cat_id, name)
            affl_url   = _affiliate_url(name)

            # Map men_ prefix back to clean category
            display_cat = cat_id.replace("men_", "") if cat_id.startswith("men_") else cat_id

            product = {
                "id":            product_id,
                "asin":          product_id,
                "name":          name,
                "category":      display_cat,
                "color":         item.get("color", "black"),
                "price":         round(float(item.get("price", 49.99)), 2),
                "style":         item.get("style_tags", ["casual", "everyday"]),
                "gender":        gender,
                "image_url":     image_url,
                "affiliate_url": affl_url,
            }
            new_products.append(product)
            existing_names.add(name.lower())
            print(f"   ✓ [{display_cat}] {name} | ${product['price']} | {product['color']}")

        print(f"   → {len(new_products)} new products so far\n")

    combined = existing + new_products
    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Total: {len(combined)} products "
          f"({len(existing)} existing + {len(new_products)} new)")

    if not args.dry_run:
        with DATA_FILE.open("w") as f:
            json.dump(combined, f, indent=2)
        print(f"✓ Written to {DATA_FILE}")
        print("\nNext step: python migrate_products.py")
    else:
        print("\nSample new products:")
        for p in new_products[:5]:
            print(f"  {p['name']} | {p['category']} | {p['color']} | ${p['price']}")


if __name__ == "__main__":
    main()
