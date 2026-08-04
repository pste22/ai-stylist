# 10 — Product Sourcing Strategy

**Status:** Updated 2026-08-03 · **Owner:** Founder/CTO · **Phase:** 3

> **Pivot (2026-08-03):** VCommission publisher application was **rejected**. Do not block demos on VCommission.
> **Now:** (1) Direct brand CSV feeds via `brand_feed_importer.py` for Snitch/D2Cs,
> (2) Apply **Cuelinks** + **Admitad** as aggregator backups,
> (3) Keep Amazon curated / Associates path,
> (4) Re-apply VCommission later with live traffic + cleaner site proof.

The single most important infrastructure decision in the company: *how does Mira get
real products with working, monetizable buy links?*

---

## 1. The decision in one line

**Use affiliate product feeds (structured APIs), never scrape retail sites ourselves.**
We are a *stylist that hands off to retailers*, not a retailer and not a data scraper.

---

## 2. Why NOT scrape "all shopping sites"

The intuitive idea — crawl every store — is a trap:

- **Legal exposure** — most retailer ToS forbid scraping. Pre-revenue litigation risk
  directly contradicts our Legal/Trust & Safety stance (`docs/09-...`).
- **Infinite maintenance** — every site redesign breaks the scraper; it becomes a
  full-time team that produces no differentiation.
- **No monetization** — scraping yields data but no commission. It bypasses the exact
  affiliate links that pay us. We'd do all the work and capture none of the value.

We don't need *all* products. We need **enough good products to style any request**,
each with a **buy link that pays us**.

---

## 3. The chosen model: affiliate networks

Affiliate networks already solved structured retail data. They provide product catalogs
(name, price, image, category) **plus a trackable buy URL** — exactly our schema
(`catalog.py` + the `affiliate_url` field in P3-2).

```
Affiliate feeds  ──normalize──▶  ProductSource adapter  ──▶  Unified catalog  ──▶  Mira
(commission + buy URLs)          (one interface)              (our schema)          recommends
                                                                                       │
                                                            Buy tap + FTC disclosure ◀─┘
                                                                       │
                                              Retailer ships / handles payment & returns
                                                       (NOT us — affiliate handoff)
```

---

## 4. Source rollout (free-first, staged)

| Stage | Source | Why this one |
|---|---|---|
| Now / demo | Local `products.json` (`LocalJsonSource`) | Zero cost; perfect persona without API risk |
| First real source | **Amazon PA-API** | Easiest signup, broad catalog; proves the adapter end-to-end |
| Fashion depth | **LTK / ShopStyle (Rakuten)** | Fashion-native, influencer-grade catalog — fits Mira's positioning |
| Scale brands | **Impact / CJ** | Direct programs with specific retailers users love (Nordstrom, ASOS…) |

### 4a. The PA-API chicken-and-egg (Amazon's 3-sale rule)

Amazon won't issue PA-API keys until you've made **3 qualifying sales**. So Amazon
ships in **two stages**, both already built behind the same `ProductSource` interface:

| Stage | Source | Keys? | What it gives |
|---|---|---|---|
| **Pre-API (launch)** | `CuratedAmazonSource` (`PRODUCT_SOURCE=curated`) | No | 10–20 hand-picked products you seed via **SiteStripe** links + manually saved images, in `data/affiliate_products.json`. Real, monetizable buy links today. |
| **Post-API (auto)** | `AmazonSource` (`PRODUCT_SOURCE=amazon`) | Yes | After 3 sales unlock keys, the API returns live catalog + images + price automatically. |

The switch is **one env var** — both sources emit the identical schema, so Mira's
reasoning, the buy flow, and the UI don't change. `amazon_affiliate_url(asin, tag)`
builds standard text affiliate links from just your Partner Tag + ASIN (no keys, no
images) as a fallback when a SiteStripe link isn't pasted in.

**Seeding workflow (pre-API):** for each product → open it on amazon.com (logged into
Associates) → SiteStripe → *Text* link → paste as `affiliate_url`, copy the 10-char
ASIN, save the image, fill name/category/price → it appears in Mira's picks.

---

## 5. Architecture: one interface, many sources (P1-12 — DONE)

The brain never knows where products come from. A single `ProductSource` interface lets
us swap or blend sources without touching Mira's reasoning.

```python
class ProductSource(Protocol):
    def search(self, *, category=None, style=None, gender=None,
               max_price=None, limit=8) -> list[dict]: ...
    def render(self, products) -> str: ...
```

- `LocalJsonSource` — Phase 1 default (implemented in `prototype/product_source.py`).
- `AmazonSource`, `LTKSource`, … — Phase 3 adapters, same interface.
- Keeps the **"stylist, not retailer"** boundary clean: we never hold inventory,
  process payment, or ship.

---

## 6. Watch-outs (track before scaling spend)

- **Catalog freshness** — feeds go stale (out-of-stock). Need a refresh/validation job
  so a "Buy" tap never embarrasses us.
- **Coverage gaps early** — one network won't have everything; Mira must gracefully say
  "I don't carry that yet" (grounding rule already enforces this).
- **Commission terms / cookie windows** vary per network — directly affects unit
  economics; model before committing marketing spend.

---

## 7. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-27 | Affiliate feeds, never self-scraping | Legal, maintenance, and monetization all favor feeds |
| 2026-06-27 | Rollout: Local → Amazon → LTK/ShopStyle → Impact/CJ | Free-first; prove adapter cheaply, then add fashion depth |
| 2026-06-27 | Build `ProductSource` adapter now (P1-12) | Makes Phase 3 a wiring task, not a rewrite |
