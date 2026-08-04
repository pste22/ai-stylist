"""
Seed the products database with real Amazon fashion products.

Supports two backends (auto-detected from .env):
  1. Rainforest API  — works immediately, no sales requirement
                       Free trial ≈ 100 requests (~1k products)
                       Business $50/mo ≈ 5k requests — enough for ~20k SKUs
  2. PA-API          — free but needs qualifying sales (often 10 / 30 days)

Usage:
  cd prototype
  python seed_from_amazon.py --limit 200                 # small test
  python seed_from_amazon.py --limit 20000 --pages 5     # expand toward +20k
  python seed_from_amazon.py --dry-run
  python seed_from_amazon.py --backend rainforest
  python seed_from_amazon.py --backend paapi

Requires in prototype/.env:
  SUPABASE_URL, SUPABASE_SECRET_KEY, AMAZON_PARTNER_TAG
  + RAINFOREST_API_KEY  OR  AMAZON_ACCESS_KEY + AMAZON_SECRET_KEY
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.insert(0, os.path.dirname(__file__))

# ── Search plan: (query, category, gender) ────────────────────────────────────
# ~400 queries × 10 items ≈ 4 000 unique products per run.
# Organised by occasion so the catalog supports full look assembly.
QUERIES: list[tuple[str, str, str]] = [

    # ════════════════════════════════════════════════════════════════
    # WOMEN — DRESSES
    # ════════════════════════════════════════════════════════════════
    # Everyday / casual
    ("Mango women midi dress",                       "dresses",    "women"),
    ("Vero Moda women dress",                        "dresses",    "women"),
    ("Only women bodycon dress",                     "dresses",    "women"),
    ("H&M women wrap dress",                         "dresses",    "women"),
    ("Marks Spencer women dress",                    "dresses",    "women"),
    ("AND women casual dress",                       "dresses",    "women"),
    ("Global Desi women print dress",                "dresses",    "women"),
    ("Mango women shirt dress",                      "dresses",    "women"),
    ("Vero Moda women floral dress",                 "dresses",    "women"),
    ("Only women mini dress",                        "dresses",    "women"),
    # Evening / cocktail
    ("Tommy Hilfiger women dress",                   "dresses",    "women"),
    ("Calvin Klein women dress",                     "dresses",    "women"),
    ("AND women cocktail dress",                     "dresses",    "women"),
    ("Mango women evening gown",                     "dresses",    "women"),
    ("H&M women sequin dress",                       "dresses",    "women"),
    ("Vero Moda women party dress",                  "dresses",    "women"),
    ("Only women satin dress",                       "dresses",    "women"),
    ("Rare Rabbit women dress",                      "dresses",    "women"),
    ("Marks Spencer women evening dress",            "dresses",    "women"),
    # Wedding guest
    ("Mango women wedding guest dress",              "dresses",    "women"),
    ("H&M women flowy maxi dress",                   "dresses",    "women"),
    ("Vero Moda women maxi dress",                   "dresses",    "women"),
    ("Calvin Klein women linen dress",               "dresses",    "women"),
    ("AND women printed maxi",                       "dresses",    "women"),
    ("Mango women ruffle dress",                     "dresses",    "women"),
    # Formal / office
    ("Van Heusen women formal dress",                "dresses",    "women"),
    ("Allen Solly women office dress",               "dresses",    "women"),
    ("Marks Spencer women work dress",               "dresses",    "women"),
    ("AND women solid shift dress",                  "dresses",    "women"),

    # ════════════════════════════════════════════════════════════════
    # WOMEN — ETHNIC WEAR
    # ════════════════════════════════════════════════════════════════
    # Sarees
    ("Biba women cotton saree",                      "ethnic",     "women"),
    ("W for woman saree",                            "ethnic",     "women"),
    ("Libas women printed saree",                    "ethnic",     "women"),
    ("Global Desi women chiffon saree",              "ethnic",     "women"),
    ("Vark women silk saree",                        "ethnic",     "women"),
    ("Kanjivaram silk saree premium",                "ethnic",     "women"),
    ("Banarasi silk saree premium",                  "ethnic",     "women"),
    ("Fabindia women cotton saree",                  "ethnic",     "women"),
    ("Suta women linen saree",                       "ethnic",     "women"),
    # Lehengas & wedding
    ("Biba women lehenga choli",                     "ethnic",     "women"),
    ("W for woman lehenga",                          "ethnic",     "women"),
    ("Libas women bridal lehenga",                   "ethnic",     "women"),
    ("Global Desi women lehenga",                    "ethnic",     "women"),
    ("AVAASA women lehenga set",                     "ethnic",     "women"),
    ("Manyavar women lehenga",                       "ethnic",     "women"),
    ("Kalki women bridal lehenga",                   "ethnic",     "women"),
    # Anarkalis & salwars
    ("Biba women anarkali suit",                     "ethnic",     "women"),
    ("W for woman anarkali",                         "ethnic",     "women"),
    ("Libas women salwar suit",                      "ethnic",     "women"),
    ("Global Desi women palazzo suit",               "ethnic",     "women"),
    ("Fabindia women salwar kameez",                 "ethnic",     "women"),
    ("Rangmanch by Pantaloons anarkali",             "ethnic",     "women"),
    # Kurtas & tops
    ("W for woman ethnic kurti",                     "ethnic",     "women"),
    ("Biba women printed kurti",                     "ethnic",     "women"),
    ("Libas women embroidered kurti",                "ethnic",     "women"),
    ("Global Desi women kurti",                      "ethnic",     "women"),
    ("Imara women kurta",                            "ethnic",     "women"),
    ("Nayo women kurti",                             "ethnic",     "women"),
    ("Aurelia women kurti",                          "ethnic",     "women"),
    ("Sangria women kurti",                          "ethnic",     "women"),
    # Indo-western fusion
    ("AND women indo-western dress",                 "ethnic",     "women"),
    ("Mango women ethnic fusion dress",              "ethnic",     "women"),
    ("H&M women kurta dress",                        "ethnic",     "women"),
    ("Only women ethnic print top",                  "ethnic",     "women"),
    ("Biba women jacket kurti",                      "ethnic",     "women"),
    ("W for woman cape dress",                       "ethnic",     "women"),

    # ════════════════════════════════════════════════════════════════
    # WOMEN — TOPS
    # ════════════════════════════════════════════════════════════════
    ("Van Heusen women formal shirt",                "tops",       "women"),
    ("Allen Solly women top",                        "tops",       "women"),
    ("Vero Moda women blouse",                       "tops",       "women"),
    ("Mango women silk blouse",                      "tops",       "women"),
    ("H&M women premium top",                        "tops",       "women"),
    ("Only women printed top",                       "tops",       "women"),
    ("Marks Spencer women shirt",                    "tops",       "women"),
    ("Tommy Hilfiger women blouse",                  "tops",       "women"),
    ("Calvin Klein women top",                       "tops",       "women"),
    ("United Colors Benetton women top",             "tops",       "women"),
    ("Superdry women crop top",                      "tops",       "women"),
    ("Mango women corset top",                       "tops",       "women"),
    ("H&M women puff sleeve top",                    "tops",       "women"),
    ("Vero Moda women cami top",                     "tops",       "women"),
    ("Only women bodysuit",                          "tops",       "women"),

    # ════════════════════════════════════════════════════════════════
    # WOMEN — BOTTOMS
    # ════════════════════════════════════════════════════════════════
    ("Levi's women skinny jeans",                    "bottoms",    "women"),
    ("Pepe Jeans women jeans",                       "bottoms",    "women"),
    ("Lee Cooper women jeans",                       "bottoms",    "women"),
    ("Vero Moda women trousers",                     "bottoms",    "women"),
    ("Only women wide leg pants",                    "bottoms",    "women"),
    ("H&M women palazzo pants",                      "bottoms",    "women"),
    ("Marks Spencer women trousers",                 "bottoms",    "women"),
    ("Tommy Hilfiger women chinos",                  "bottoms",    "women"),
    ("Mango women tailored trousers",                "bottoms",    "women"),
    ("Levi's women wide leg jeans",                  "bottoms",    "women"),
    ("Vero Moda women straight jeans",               "bottoms",    "women"),
    ("H&M women midi skirt",                         "bottoms",    "women"),
    ("Mango women pleated skirt",                    "bottoms",    "women"),
    ("Only women mini skirt",                        "bottoms",    "women"),
    ("AND women culottes",                           "bottoms",    "women"),

    # ════════════════════════════════════════════════════════════════
    # WOMEN — OUTERWEAR & BLAZERS
    # ════════════════════════════════════════════════════════════════
    ("Mango women trench coat",                      "outerwear",  "women"),
    ("Tommy Hilfiger women jacket",                  "outerwear",  "women"),
    ("Superdry women jacket",                        "outerwear",  "women"),
    ("H&M women blazer",                             "outerwear",  "women"),
    ("Vero Moda women blazer",                       "outerwear",  "women"),
    ("United Colors Benetton women jacket",          "outerwear",  "women"),
    ("Mango women structured blazer",                "outerwear",  "women"),
    ("Only women oversized blazer",                  "outerwear",  "women"),
    ("Marks Spencer women blazer",                   "outerwear",  "women"),
    ("Calvin Klein women coat",                      "outerwear",  "women"),
    ("AND women formal blazer",                      "outerwear",  "women"),
    ("Vero Moda women denim jacket",                 "outerwear",  "women"),
    ("H&M women puffer jacket",                      "outerwear",  "women"),
    ("Superdry women windcheater",                   "outerwear",  "women"),
    ("Tommy Hilfiger women parka",                   "outerwear",  "women"),

    # ════════════════════════════════════════════════════════════════
    # WOMEN — SHOES
    # ════════════════════════════════════════════════════════════════
    # Heels & pumps
    ("Steve Madden women heels",                     "shoes",      "women"),
    ("Carlton London women pumps",                   "shoes",      "women"),
    ("Aldo women ankle boots",                       "shoes",      "women"),
    ("Charles Keith women heels",                    "shoes",      "women"),
    ("Catwalk women block heels",                    "shoes",      "women"),
    ("Mango women stiletto heels",                   "shoes",      "women"),
    ("Steve Madden women block heels",               "shoes",      "women"),
    ("Aldo women strappy heels",                     "shoes",      "women"),
    ("Carlton London women kitten heels",            "shoes",      "women"),
    # Flats & sandals
    ("Clarks women ballet flats",                    "shoes",      "women"),
    ("Mango women leather sandals",                  "shoes",      "women"),
    ("Aldo women flat sandals",                      "shoes",      "women"),
    ("Steve Madden women slide sandals",             "shoes",      "women"),
    ("Clarks women gladiator sandals",               "shoes",      "women"),
    ("Fabindia women juttis",                        "shoes",      "women"),
    ("Mochi women ethnic flats",                     "shoes",      "women"),
    ("Dune London women sandals",                    "shoes",      "women"),
    # Sneakers & casual
    ("Tommy Hilfiger women sneakers",                "shoes",      "women"),
    ("Nike women sneakers",                          "shoes",      "women"),
    ("Adidas women shoes",                           "shoes",      "women"),
    ("Reebok women classic shoes",                   "shoes",      "women"),
    ("Vans women canvas shoes",                      "shoes",      "women"),
    ("New Balance women sneakers",                   "shoes",      "women"),
    # Boots
    ("Aldo women ankle boots",                       "shoes",      "women"),
    ("Steve Madden women knee boots",                "shoes",      "women"),
    ("Clarks women leather boots",                   "shoes",      "women"),
    ("Mango women chelsea boots",                    "shoes",      "women"),

    # ════════════════════════════════════════════════════════════════
    # WOMEN — BAGS
    # ════════════════════════════════════════════════════════════════
    # Clutches & evening bags
    ("Charles Keith women clutch",                   "bags",       "women"),
    ("Aldo women evening clutch",                    "bags",       "women"),
    ("Lavie women clutch purse",                     "bags",       "women"),
    ("Caprese women evening bag",                    "bags",       "women"),
    ("Mango women satin clutch",                     "bags",       "women"),
    # Crossbody & sling
    ("Fossil women crossbody bag",                   "bags",       "women"),
    ("Aldo women crossbody",                         "bags",       "women"),
    ("Tommy Hilfiger women sling bag",               "bags",       "women"),
    ("Charles Keith women shoulder bag",             "bags",       "women"),
    ("Caprese women crossbody",                      "bags",       "women"),
    ("Lavie women sling bag",                        "bags",       "women"),
    # Totes & work bags
    ("Hidesign women leather tote",                  "bags",       "women"),
    ("Caprese women tote bag",                       "bags",       "women"),
    ("Tommy Hilfiger women tote",                    "bags",       "women"),
    ("Marks Spencer women work bag",                 "bags",       "women"),
    ("Fossil women leather tote",                    "bags",       "women"),
    # Handbags
    ("Lavie women handbag",                          "bags",       "women"),
    ("Hidesign women leather bag",                   "bags",       "women"),
    ("Aldo women shoulder bag",                      "bags",       "women"),
    ("Tommy Hilfiger women handbag",                 "bags",       "women"),
    ("Caprese women handbag",                        "bags",       "women"),
    ("Baggit women vegan leather bag",               "bags",       "women"),

    # ════════════════════════════════════════════════════════════════
    # WOMEN — ACCESSORIES (watches, jewellery, sunglasses, scarves)
    # ════════════════════════════════════════════════════════════════
    # Watches
    ("Fossil women watch",                           "accessories","women"),
    ("Titan women watch",                            "accessories","women"),
    ("Daniel Wellington women watch",                "accessories","women"),
    ("Michael Kors women watch",                     "accessories","women"),
    ("Tommy Hilfiger women watch",                   "accessories","women"),
    ("Casio women watch",                            "accessories","women"),
    ("Timex women watch",                            "accessories","women"),
    # Sunglasses
    ("Ray-Ban women sunglasses",                     "accessories","women"),
    ("Michael Kors women sunglasses",                "accessories","women"),
    ("Vogue Eyewear women sunglasses",               "accessories","women"),
    ("Fastrack women sunglasses",                    "accessories","women"),
    ("Titan women sunglasses",                       "accessories","women"),
    ("Tommy Hilfiger women sunglasses",              "accessories","women"),
    # Jewellery
    ("Guess women necklace",                         "accessories","women"),
    ("Swarovski women bracelet",                     "accessories","women"),
    ("Voylla women earrings",                        "accessories","women"),
    ("Tanishq women gold earrings",                  "accessories","women"),
    ("Mia by Tanishq women necklace",                "accessories","women"),
    ("Sukkhi women jewellery set",                   "accessories","women"),
    ("Zaveri Pearls women necklace set",             "accessories","women"),
    ("Johareez women ethnic jewellery",              "accessories","women"),
    ("Outhouse women statement earrings",            "accessories","women"),
    ("Amrapali women silver jewellery",              "accessories","women"),
    # Scarves & belts
    ("Mango women silk scarf",                       "accessories","women"),
    ("H&M women belt",                               "accessories","women"),
    ("Tommy Hilfiger women belt",                    "accessories","women"),
    ("Mango women leather belt",                     "accessories","women"),
    ("Pashmina shawl women premium",                 "accessories","women"),
    ("Fabindia women stole dupatta",                 "accessories","women"),

    # ════════════════════════════════════════════════════════════════
    # WOMEN — ACTIVEWEAR
    # ════════════════════════════════════════════════════════════════
    ("Nike women sports bra",                        "activewear", "women"),
    ("Adidas women leggings",                        "activewear", "women"),
    ("Puma women gym top",                           "activewear", "women"),
    ("Under Armour women activewear",                "activewear", "women"),
    ("Reebok women training shoes",                  "activewear", "women"),
    ("Nike women training tights",                   "activewear", "women"),
    ("Adidas women yoga pants",                      "activewear", "women"),
    ("Puma women running shoes",                     "activewear", "women"),
    ("Nike women windbreaker",                       "activewear", "women"),
    ("Adidas women track jacket",                    "activewear", "women"),

    # ════════════════════════════════════════════════════════════════
    # MEN — TOPS & SHIRTS
    # ════════════════════════════════════════════════════════════════
    ("Tommy Hilfiger men polo shirt",                "tops",       "men"),
    ("Calvin Klein men t-shirt",                     "tops",       "men"),
    ("Van Heusen men formal shirt",                  "tops",       "men"),
    ("Arrow men shirt",                              "tops",       "men"),
    ("Allen Solly men shirt",                        "tops",       "men"),
    ("Peter England men formal shirt",               "tops",       "men"),
    ("Raymond men shirt",                            "tops",       "men"),
    ("Superdry men t-shirt",                         "tops",       "men"),
    ("Marks Spencer men shirt",                      "tops",       "men"),
    ("United Colors Benetton men shirt",             "tops",       "men"),
    ("Tommy Hilfiger men slim fit shirt",            "tops",       "men"),
    ("Lacoste men polo",                             "tops",       "men"),
    ("Fred Perry men polo shirt",                    "tops",       "men"),
    ("Jack Jones men casual shirt",                  "tops",       "men"),
    ("Mango men shirt",                              "tops",       "men"),
    ("H&M men shirt",                                "tops",       "men"),
    ("Zara men shirt india",                         "tops",       "men"),
    ("Rare Rabbit men shirt",                        "tops",       "men"),
    ("Celio men casual shirt",                       "tops",       "men"),
    ("Wrogn men graphic tee",                        "tops",       "men"),

    # ════════════════════════════════════════════════════════════════
    # MEN — ETHNIC
    # ════════════════════════════════════════════════════════════════
    ("Manyavar men sherwani",                        "ethnic",     "men"),
    ("Manyavar men kurta pajama",                    "ethnic",     "men"),
    ("Manyavar men nehru jacket",                    "ethnic",     "men"),
    ("Fabindia men kurta",                           "ethnic",     "men"),
    ("Raymond men kurta",                            "ethnic",     "men"),
    ("Biba men kurta set",                           "ethnic",     "men"),
    ("Ethnix by Raymond men sherwani",               "ethnic",     "men"),
    ("Kalyan Silks men kurta",                       "ethnic",     "men"),
    ("W for men kurta",                              "ethnic",     "men"),
    ("Sojanya men silk kurta",                       "ethnic",     "men"),
    ("Libas men cotton kurta",                       "ethnic",     "men"),
    ("Manyavar men Indo western",                    "ethnic",     "men"),
    ("Manyavar men jodhpuri suit",                   "ethnic",     "men"),

    # ════════════════════════════════════════════════════════════════
    # MEN — BOTTOMS
    # ════════════════════════════════════════════════════════════════
    ("Levi's men slim fit jeans",                    "bottoms",    "men"),
    ("Pepe Jeans men jeans",                         "bottoms",    "men"),
    ("Van Heusen men formal trousers",               "bottoms",    "men"),
    ("Arrow men chinos",                             "bottoms",    "men"),
    ("Allen Solly men trousers",                     "bottoms",    "men"),
    ("Lee men jeans",                                "bottoms",    "men"),
    ("Tommy Hilfiger men chino pants",               "bottoms",    "men"),
    ("Levi's men straight fit jeans",                "bottoms",    "men"),
    ("Jack Jones men slim jeans",                    "bottoms",    "men"),
    ("Mango men trousers",                           "bottoms",    "men"),
    ("H&M men slim trousers",                        "bottoms",    "men"),
    ("Peter England men formal trousers",            "bottoms",    "men"),
    ("Raymond men trouser",                          "bottoms",    "men"),

    # ════════════════════════════════════════════════════════════════
    # MEN — OUTERWEAR, SUITS & BLAZERS
    # ════════════════════════════════════════════════════════════════
    ("Tommy Hilfiger men jacket",                    "outerwear",  "men"),
    ("Superdry men bomber jacket",                   "outerwear",  "men"),
    ("United Colors Benetton men jacket",            "outerwear",  "men"),
    ("Mango men blazer",                             "outerwear",  "men"),
    ("Van Heusen men blazer",                        "outerwear",  "men"),
    ("Raymond men suit",                             "outerwear",  "men"),
    ("Arrow men blazer",                             "outerwear",  "men"),
    ("Allen Solly men blazer",                       "outerwear",  "men"),
    ("Tommy Hilfiger men sport coat",                "outerwear",  "men"),
    ("Peter England men suit",                       "outerwear",  "men"),
    ("Jack Jones men leather jacket",                "outerwear",  "men"),
    ("H&M men blazer",                               "outerwear",  "men"),
    ("Marks Spencer men suit jacket",                "outerwear",  "men"),
    ("Superdry men puffer jacket",                   "outerwear",  "men"),
    ("Celio men overcoat",                           "outerwear",  "men"),

    # ════════════════════════════════════════════════════════════════
    # MEN — SHOES
    # ════════════════════════════════════════════════════════════════
    # Formal
    ("Red Tape men leather shoes",                   "shoes",      "men"),
    ("Clarks men formal shoes",                      "shoes",      "men"),
    ("Hush Puppies men loafers",                     "shoes",      "men"),
    ("Bata men formal shoes",                        "shoes",      "men"),
    ("Woodland men leather shoes",                   "shoes",      "men"),
    ("Lee Cooper men formal shoes",                  "shoes",      "men"),
    # Sneakers & casual
    ("Tommy Hilfiger men sneakers",                  "shoes",      "men"),
    ("Adidas men sneakers",                          "shoes",      "men"),
    ("Nike men running shoes",                       "shoes",      "men"),
    ("New Balance men sneakers",                     "shoes",      "men"),
    ("Puma men sneakers",                            "shoes",      "men"),
    ("Reebok men classic shoes",                     "shoes",      "men"),
    ("Vans men canvas shoes",                        "shoes",      "men"),
    ("Skechers men shoes",                           "shoes",      "men"),
    ("Converse men sneakers",                        "shoes",      "men"),
    # Boots & ethnic
    ("Woodland men boots",                           "shoes",      "men"),
    ("Red Tape men ankle boots",                     "shoes",      "men"),
    ("Clarks men desert boots",                      "shoes",      "men"),
    ("Punjabi Jutti men ethnic shoes",               "shoes",      "men"),
    ("Mochi men kolhapuri shoes",                    "shoes",      "men"),

    # ════════════════════════════════════════════════════════════════
    # MEN — BAGS & WALLETS
    # ════════════════════════════════════════════════════════════════
    ("Tommy Hilfiger men messenger bag",             "bags",       "men"),
    ("Fossil men wallet leather",                    "bags",       "men"),
    ("Hidesign men leather bag",                     "bags",       "men"),
    ("Fossil men backpack",                          "bags",       "men"),
    ("Tommy Hilfiger men backpack",                  "bags",       "men"),
    ("American Tourister men laptop bag",            "bags",       "men"),
    ("Samsonite men briefcase",                      "bags",       "men"),
    ("Hidesign men leather wallet",                  "bags",       "men"),
    ("Woodland men laptop bag",                      "bags",       "men"),
    ("Tommy Hilfiger men tote",                      "bags",       "men"),

    # ════════════════════════════════════════════════════════════════
    # MEN — ACCESSORIES
    # ════════════════════════════════════════════════════════════════
    # Watches
    ("Fossil men watch",                             "accessories","men"),
    ("Titan men watch",                              "accessories","men"),
    ("Ray-Ban men sunglasses",                       "accessories","men"),
    ("Tommy Hilfiger men belt",                      "accessories","men"),
    ("Daniel Wellington men watch",                  "accessories","men"),
    ("Casio men G-Shock watch",                      "accessories","men"),
    ("Timex men watch",                              "accessories","men"),
    ("Fastrack men watch",                           "accessories","men"),
    ("Seiko men watch",                              "accessories","men"),
    # Sunglasses
    ("Ray-Ban men sunglasses",                       "accessories","men"),
    ("Fastrack men sunglasses",                      "accessories","men"),
    ("Carrera men sunglasses",                       "accessories","men"),
    ("Tommy Hilfiger men sunglasses",                "accessories","men"),
    ("Titan men sunglasses",                         "accessories","men"),
    # Belts & ties
    ("Tommy Hilfiger men leather belt",              "accessories","men"),
    ("Arrow men formal tie",                         "accessories","men"),
    ("Van Heusen men tie",                           "accessories","men"),
    ("Peter England men cufflinks",                  "accessories","men"),
    ("Hidesign men leather belt",                    "accessories","men"),
    ("Tommy Hilfiger men pocket square",             "accessories","men"),

    # ════════════════════════════════════════════════════════════════
    # MEN — ACTIVEWEAR
    # ════════════════════════════════════════════════════════════════
    ("Nike men dri-fit t-shirt",                     "activewear", "men"),
    ("Adidas men training shorts",                   "activewear", "men"),
    ("Puma men gym wear",                            "activewear", "men"),
    ("Under Armour men compression",                 "activewear", "men"),
    ("Nike men track pants",                         "activewear", "men"),
    ("Adidas men jogger pants",                      "activewear", "men"),
    ("Reebok men running shoes",                     "activewear", "men"),
    ("Nike men basketball shoes",                    "activewear", "men"),
    ("Puma men training jacket",                     "activewear", "men"),
    ("Under Armour men shorts",                      "activewear", "men"),

    # ════════════════════════════════════════════════════════════════
    # OCCASION-SPECIFIC SEARCH BOOSTS
    # ════════════════════════════════════════════════════════════════
    # Sangeet / Mehndi
    ("sangeet outfit women lehenga",                 "ethnic",     "women"),
    ("mehndi outfit women yellow suit",              "ethnic",     "women"),
    ("haldi outfit women yellow ethnic",             "ethnic",     "women"),
    ("sangeet outfit men kurta pajama",              "ethnic",     "men"),
    # Wedding reception
    ("reception saree silk premium",                 "ethnic",     "women"),
    ("reception lehenga embroidered",                "ethnic",     "women"),
    ("groom sherwani reception",                     "ethnic",     "men"),
    # Diwali / Navratri / Festive
    ("Diwali outfit women ethnic wear",              "ethnic",     "women"),
    ("Navratri chaniya choli women",                 "ethnic",     "women"),
    ("festive kurti women silk",                     "ethnic",     "women"),
    ("festive kurta men silk",                       "ethnic",     "men"),
    ("Diwali party dress women",                     "dresses",    "women"),
    # Date night
    ("date night dress women",                       "dresses",    "women"),
    ("date night women heels",                       "shoes",      "women"),
    ("date night women clutch",                      "bags",       "women"),
    # Beach / vacation
    ("resort wear women dress",                      "dresses",    "women"),
    ("beach cover-up women",                         "dresses",    "women"),
    ("vacation outfit women linen",                  "tops",       "women"),
    ("resort wear men shirt linen",                  "tops",       "men"),
    # Birthday party
    ("birthday party dress women",                   "dresses",    "women"),
    ("birthday party outfit men casual",             "tops",       "men"),
    # Office party
    ("office party women dress",                     "dresses",    "women"),
    ("smart casual men blazer party",                "outerwear",  "men"),
    # Cocktail evening
    ("cocktail party dress women",                   "dresses",    "women"),
    ("cocktail women heels",                         "shoes",      "women"),
    ("cocktail women clutch",                        "bags",       "women"),
    ("cocktail men suit",                            "outerwear",  "men"),
]

_COLOR_WORDS = {
    "black", "white", "navy", "beige", "brown", "grey", "gray",
    "blue", "red", "pink", "green", "yellow", "orange", "purple",
    "cream", "tan", "camel", "olive", "burgundy", "blush", "sage",
    "khaki", "charcoal", "indigo", "rust", "gold", "silver", "nude",
    "coral", "teal", "lavender", "mint", "ivory",
}


def _extract_color(name: str) -> str:
    nl = name.lower()
    for c in _COLOR_WORDS:
        if c in nl:
            return c
    return "multi"


def _make_id(asin: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"amazon:{asin}"))


def _detect_backend() -> str:
    has_rainforest = bool(os.environ.get("RAINFOREST_API_KEY"))
    has_paapi      = bool(os.environ.get("AMAZON_ACCESS_KEY")) and \
                     bool(os.environ.get("AMAZON_SECRET_KEY"))
    if has_rainforest:
        return "rainforest"
    if has_paapi:
        return "paapi"
    return "none"


def _fetch(
    backend: str,
    query: str,
    *,
    page: int = 1,
    sort_by: str = "average_review",
) -> list[dict]:
    if backend == "rainforest":
        from rainforest_products import search_products
        return search_products(query, page=page, sort_by=sort_by)
    if backend == "paapi":
        # PA-API SearchItems has no deep pagination here — page>1 returns []
        if page > 1:
            return []
        from amazon_pa_api import search_items
        return search_items(query)
    raise EnvironmentError("no-backend")


def _load_existing_asins(sb) -> set[str]:
    """Page through Supabase — select('*') caps around 1k rows otherwise."""
    seen: set[str] = set()
    page_size = 1000
    start = 0
    while True:
        end = start + page_size - 1
        res = sb.table("products").select("asin").range(start, end).execute()
        rows = res.data or []
        for r in rows:
            if r.get("asin"):
                seen.add(r["asin"])
        if len(rows) < page_size:
            break
        start += page_size
    return seen


def _flush_batch(sb, batch: list[dict], dry_run: bool) -> int:
    if not batch:
        return 0
    if dry_run:
        return len(batch)
    sb.table("products").upsert(batch, on_conflict="id").execute()
    return len(batch)


def run(
    limit: int = 1000,
    dry_run: bool = False,
    replace: bool = False,
    backend: str = "auto",
    pages: int = 1,
    min_price: float = 1500.0,
    sleep_s: float = 1.2,
    batch_size: int = 40,
) -> None:

    from supabase import create_client
    sb  = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    tag = os.environ.get("AMAZON_PARTNER_TAG", "")

    if backend == "auto":
        backend = _detect_backend()

    if backend == "none":
        print("""
❌  No product API credentials found — cannot pull Amazon products yet.

You already have ~1k SKUs in Supabase. To add ~20k MORE real Amazon affiliates:

  Option A — Rainforest API (fastest path to 20k):
    1. https://www.rainforestapi.com/  → start trial / Business plan
       Free trial ≈ 100 requests (~1k products)
       ~20k new SKUs needs ~2–2.5k search requests (pages × queries)
       Business ($50/mo, 5k req) is enough for one expansion run
    2. Add to prototype/.env:
         RAINFOREST_API_KEY=your_key_here
    3. Re-run:
         .venv/bin/python seed_from_amazon.py --limit 20000 --pages 5

  Option B — Amazon PA-API (free, sales-gated):
    1. Qualify for API access (typically ~10 sales / 30 days)
    2. Add AMAZON_ACCESS_KEY + AMAZON_SECRET_KEY to prototype/.env
    3. Re-run (fewer unique SKUs per query — may need more query days)

Partner tag alone is NOT enough — Amazon will not let us invent ASINs.
""")
        sys.exit(1)

    pages = max(1, pages)
    if backend == "paapi" and pages > 1:
        print("Note: PA-API path only uses page 1 per query in this script.")
        pages = 1

    est_requests = len(QUERIES) * pages
    print(f"Backend: {backend.upper()}  |  Partner tag: {tag or '(none)'}")
    print(f"Target new inserts: {limit}  |  pages/query: {pages}  |  "
          f"max API calls ≈ {est_requests}  |  min price ₹{min_price:.0f}")

    if replace and not dry_run:
        print("Clearing existing amazon-source products…")
        sb.table("products").delete().eq("source", "amazon").execute()

    seen_asins = _load_existing_asins(sb)
    print(f"Products already in DB (with ASIN): {len(seen_asins)}\n")

    inserted = skipped = errors = requests_made = 0
    batch: list[dict] = []

    for query, category, gender in QUERIES:
        if inserted >= limit:
            break
        for page in range(1, pages + 1):
            if inserted >= limit:
                break
            print(f"🔍  {query!r}  p{page} → {category}/{gender}", flush=True)
            try:
                items = _fetch(backend, query, page=page, sort_by="average_review")
                requests_made += 1
            except EnvironmentError as e:
                print(f"\n❌  {e}")
                sys.exit(1)
            except RuntimeError as e:
                print(f"   API error: {e}")
                errors += 1
                time.sleep(max(3.0, sleep_s * 2))
                continue

            if not items:
                print("   (empty page — stopping deeper pages for this query)")
                break

            for item in items:
                if inserted >= limit:
                    break
                asin = item.get("asin", "")
                if not asin or asin in seen_asins:
                    skipped += 1
                    continue
                if not item.get("image_url"):
                    skipped += 1
                    continue
                price = item.get("price", 0)
                if not price or float(price) < min_price:
                    skipped += 1
                    continue

                seen_asins.add(asin)
                row = {
                    "id":            _make_id(asin),
                    "source":        "amazon",
                    "asin":          asin,
                    "name":          item["name"],
                    "category":      category,
                    "color":         _extract_color(item["name"]),
                    "price":         price,
                    "currency":      "INR",
                    "style":         [],
                    "gender":        gender,
                    "image_url":     item["image_url"],
                    "affiliate_url": item["affiliate_url"],
                    "partner_tag":   tag,
                    "is_active":     True,
                }
                if dry_run:
                    print(f"  DRY  {asin}  ₹{price:>8.0f}  {item['name'][:60]}")
                    inserted += 1
                else:
                    batch.append(row)
                    inserted += 1
                    if len(batch) >= batch_size:
                        _flush_batch(sb, batch, dry_run=False)
                        print(f"  ⬆ flushed {len(batch)}  (total new={inserted})")
                        batch.clear()

            time.sleep(sleep_s)

        if inserted and inserted % 500 < batch_size:
            print(f"… progress: inserted={inserted}  skipped={skipped}  "
                  f"api_calls={requests_made}", flush=True)

    if batch and not dry_run:
        _flush_batch(sb, batch, dry_run=False)
        print(f"  ⬆ flushed final {len(batch)}")

    print(
        f"\n{'[DRY RUN] ' if dry_run else ''}"
        f"✅  inserted={inserted}  skipped={skipped}  errors={errors}  "
        f"api_calls={requests_made}"
    )
    if inserted < limit:
        print(
            f"⚠️  Only got {inserted}/{limit}. "
            "Raise --pages, add more QUERIES, or lower --min-price."
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed DB with real Amazon fashion products")
    ap.add_argument("--limit", type=int, default=1000,
                    help="max NEW products to insert (use 20000 for big expand)")
    ap.add_argument("--pages", type=int, default=1,
                    help="Rainforest result pages per query (use 5 for ~20k scale)")
    ap.add_argument("--min-price", type=float, default=1500.0,
                    help="skip items cheaper than this INR amount")
    ap.add_argument("--sleep", type=float, default=1.2,
                    help="seconds between API calls")
    ap.add_argument("--dry-run", action="store_true", help="print without writing to DB")
    ap.add_argument("--replace", action="store_true", help="delete existing amazon rows first")
    ap.add_argument("--backend", choices=["auto", "rainforest", "paapi"], default="auto")
    args = ap.parse_args()
    run(
        limit=args.limit,
        dry_run=args.dry_run,
        replace=args.replace,
        backend=args.backend,
        pages=args.pages,
        min_price=args.min_price,
        sleep_s=args.sleep,
    )
