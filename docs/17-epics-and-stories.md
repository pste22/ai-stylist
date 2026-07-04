# Mira AI Stylist — Epics, User Stories & Implementation Order

_Derived from Harvard market strategy review + sales team consultation (July 2026)._  
_Format: Epic → Stories → Acceptance Criteria → Priority / Effort / Value._

---

## How to Read This Document

**Priority tiers**
- 🔴 **P0 — Gate** : Must be done before ANY real user touches the app. Bugs or blockers.
- 🟠 **P1 — Launch** : Required to call this a real product worth sharing.
- 🟡 **P2 — Monetise** : Turns traffic into revenue and data.
- 🟢 **P3 — Retain** : Keeps users coming back.
- 🔵 **P4 — Scale** : Platform and B2B plays.

**Effort** (eng-days, solo developer)  
`XS` < 1 day · `S` 1–2 days · `M` 3–5 days · `L` 1–2 weeks · `XL` 2–4 weeks

**Value score** (1–10): business impact if shipped × user impact if missing

---

## Recommended Sprint Order (6 sprints × 1 week)

| Sprint | Theme | Epics |
|--------|-------|-------|
| **S1** | Survival | E1 Catalog · E6 Error States · E9 Privacy |
| **S2** | Mobile-first | E2 Mobile/PWA · E7 Rate Limiting |
| **S3** | Growth loop | E3 Sharing · E4 Email Capture |
| **S4** | Money | E5 Amazon PA-API · E8 Analytics |
| **S5** | Retention | E10 User Profile · E11 Outfit Completion |
| **S6** | Scale | E12 White-label · E13 Brand Partnerships |

---

---

# 🔴 P0 — Gate (must ship before real users)

---

## E1 · Catalog Expansion

> **Why first**: 9 products means Mira fails 80 % of requests. Every other improvement is wasted if she says "I don't have that."

**Epic goal**: Reach 200+ products across all 6 categories (dresses, tops, bottoms, outerwear, shoes, accessories) with real images, real affiliate links, and accurate metadata.

---

### Story E1-1 · Manual SiteStripe batch seeding
**As a** product manager  
**I want** 50 products added per day via Amazon SiteStripe  
**So that** Mira has enough catalog depth to handle a realistic range of shopper requests

**Acceptance criteria**
- [ ] Each product has: ASIN, name, category, color, price, style tags, gender, image_url, affiliate_url
- [ ] No product has a null image_url (image must render in the chat card)
- [ ] Products cover at least: 3 dress styles, 4 bottom styles, 4 top styles, 2 outerwear, 3 shoe styles, 3 accessories
- [ ] All ASINs verified as currently in-stock on Amazon before inserting
- [ ] migrate_products.py --dry-run passes with 0 errors before each batch import

**Priority**: 🔴 P0 · **Effort**: S per 50 products · **Value**: 10/10

---

### Story E1-2 · Curated affiliate feed integration (Impact / CJ Affiliate)
**As a** developer  
**I want** a feed importer that pulls products from a third-party affiliate network  
**So that** catalog can grow to 1 000+ products without manual SiteStripe work

**Acceptance criteria**
- [ ] Script fetches product feed (CSV or API) from Impact or CJ
- [ ] Maps feed fields to Supabase products schema
- [ ] Deduplicates by ASIN before inserting
- [ ] Runs on a cron (daily refresh)
- [ ] Only imports products with valid image_url

**Priority**: 🟠 P1 · **Effort**: M · **Value**: 9/10

---

### Story E1-3 · Catalog admin UI
**As a** content manager  
**I want** a simple web page to add, edit, and deactivate products  
**So that** I don't need to run Python scripts or open Supabase Studio for every catalog change

**Acceptance criteria**
- [ ] Protected by a simple password (env var)
- [ ] Can add a product by pasting an Amazon URL (scrapes ASIN + name + image)
- [ ] Can toggle is_active without deleting (preserves FK integrity with events)
- [ ] Shows current product count by category

**Priority**: 🟠 P1 · **Effort**: M · **Value**: 7/10

---

## E2 · Mobile Experience & PWA

> **Why P0**: 73 % of fashion shopping is on mobile. If it doesn't work on a phone, it doesn't exist.

**Epic goal**: App is fully usable on a phone browser, installable as a PWA, and the text-mode chat is the default on mobile.

---

### Story E2-1 · Responsive CSS for chat layout
**As a** mobile shopper  
**I want** the chat UI to fill my phone screen properly  
**So that** I can use Mira on my phone without pinching or horizontal scrolling

**Acceptance criteria**
- [ ] No horizontal scroll on viewport widths 320 px–430 px
- [ ] Chat input stays above the keyboard (use `env(safe-area-inset-bottom)`)
- [ ] Product-line cards are readable at 375 px width
- [ ] Bubble max-width adjusts to 90 % on mobile (vs 72 % on desktop)
- [ ] Tested on Chrome/Safari iOS and Chrome Android

**Priority**: 🔴 P0 · **Effort**: S · **Value**: 9/10

---

### Story E2-2 · Progressive Web App manifest
**As a** returning user  
**I want** to add Mira to my home screen  
**So that** I can open her like a native app without going through a browser

**Acceptance criteria**
- [ ] `manifest.json` with name, icons (192 px + 512 px), theme_color, display: standalone
- [ ] Service worker caches shell (offline shows "Mira is offline" gracefully)
- [ ] iOS splash screen meta tags present
- [ ] Lighthouse PWA score ≥ 80

**Priority**: 🟠 P1 · **Effort**: S · **Value**: 7/10

---

### Story E2-3 · Mobile-first text mode as default
**As a** mobile user  
**I want** the app to default to text/silent mode  
**So that** I don't need to grant mic permissions just to browse

**Acceptance criteria**
- [ ] On first visit, detect if device is mobile (UA or screen width < 768 px) → default to text mode
- [ ] Voice mode still accessible via toggle
- [ ] Mode preference saved to localStorage

**Priority**: 🔴 P0 · **Effort**: XS · **Value**: 8/10

---

## E6 · Error States & Reliability

> **Why P0**: Right now a dropped bridge = blank screen. That's a trust-killer.

---

### Story E6-1 · Friendly offline / bridge-down state
**As a** user  
**I want** a helpful message when the server is unavailable  
**So that** I don't think the app is broken and leave forever

**Acceptance criteria**
- [ ] WebSocket connection failure shows: "Mira is taking a quick break — try again in a moment"
- [ ] "Retry" button attempts reconnect
- [ ] After 3 failed retries, shows "Something's wrong on our end. We'll be back soon."
- [ ] No raw error messages or stack traces visible to the user

**Priority**: 🔴 P0 · **Effort**: XS · **Value**: 8/10

---

### Story E6-2 · Session reconnect with context
**As a** user mid-conversation  
**I want** Mira to reconnect automatically if the session drops  
**So that** I don't lose my conversation and have to start over

**Acceptance criteria**
- [ ] Bridge auto-reconnects using Gemini resumption handle (already implemented)
- [ ] Browser shows "Reconnecting…" avatar state during gap
- [ ] On reconnect, Mira says a brief "Sorry about that — where were we?" without repeating context
- [ ] If reconnect fails after 3 attempts, show the offline state (E6-1)

**Priority**: 🔴 P0 · **Effort**: S · **Value**: 9/10

---

### Story E6-3 · Load test: 20 concurrent users
**As a** founder  
**I want** to know the app works under light real-world load  
**So that** a social post or press mention doesn't take the service down

**Acceptance criteria**
- [ ] Locust or k6 load test script written and committed
- [ ] 20 simultaneous WebSocket connections hold for 5 minutes without crash
- [ ] P95 latency for first Mira response ≤ 4 s under load
- [ ] Document the bottleneck (Gemini API concurrency limit, server RAM, etc.)

**Priority**: 🔴 P0 · **Effort**: S · **Value**: 8/10

---

## E7 · Rate Limiting & Security

---

### Story E7-1 · Per-IP connection limit
**As a** platform operator  
**I want** to cap WebSocket connections per IP  
**So that** one person or bot can't exhaust the Gemini API quota for all users

**Acceptance criteria**
- [ ] Max 3 concurrent sessions per IP
- [ ] Max 10 session starts per IP per hour
- [ ] Excess requests get a JSON error: `{"type":"error","message":"Too many sessions — try again shortly"}`
- [ ] Limits configurable via env vars

**Priority**: 🔴 P0 · **Effort**: XS · **Value**: 8/10

---

### Story E7-2 · API key & secret rotation checklist
**As a** security-conscious developer  
**I want** all secrets stored safely and rotatable without code changes  
**So that** a leaked key doesn't require a redeploy

**Acceptance criteria**
- [ ] All secrets in `.env` / Codespaces/Render secrets — never committed
- [ ] `.env.example` lists required keys with placeholder values
- [ ] README documents how to rotate each key (Gemini, Supabase, GROQ)
- [ ] No hardcoded keys anywhere in git history (run `git log -p | grep -i "api_key"`)

**Priority**: 🔴 P0 · **Effort**: XS · **Value**: 9/10

---

## E9 · Privacy & Legal Compliance

> **Why P0**: GDPR/CCPA apply the moment a real user from the EU or California touches the app.

---

### Story E9-1 · Privacy policy & cookie banner
**As a** user  
**I want** to know what data Mira stores about me  
**So that** I can make an informed choice about using the app

**Acceptance criteria**
- [ ] Privacy policy page exists (can be a simple `/privacy` route or modal)
- [ ] Covers: what is stored (user_id, name, product interactions), how long, who has access
- [ ] Cookie/localStorage consent banner on first visit
- [ ] Link to privacy policy in app footer

**Priority**: 🔴 P0 · **Effort**: S · **Value**: 8/10

---

### Story E9-2 · Right-to-delete endpoint
**As a** user  
**I want** to delete my account and all my data  
**So that** I can exercise my GDPR right to erasure

**Acceptance criteria**
- [ ] `DELETE /user` endpoint (authenticated by user_id token) deletes: users, user_preferences, user_history rows
- [ ] Cascades handled by FK `ON DELETE CASCADE` (already in schema)
- [ ] Confirmation email sent (or in-app confirmation)
- [ ] Button accessible from user profile page

**Priority**: 🔴 P0 · **Effort**: S · **Value**: 7/10

---

---

# 🟠 P1 — Launch (required to call this a real product)

---

## E3 · Viral Sharing Loop

> **Why P1**: Zero-cost user acquisition. One good session → shareable card → new users.

**Epic goal**: Every session can produce a shareable "Mira's picks for you" card that drives new signups.

---

### Story E3-1 · Session summary card
**As a** shopper  
**I want** a visual summary of what Mira picked for me  
**So that** I can share it with friends or save it for later

**Acceptance criteria**
- [ ] At end of conversation, "See your session" button appears
- [ ] Summary card shows: Mira avatar, 2–4 saved/recommended products (image + name + price), total outfit value, "Styled by Mira" branding
- [ ] Card is a shareable URL (e.g. `/session/abc123`) that anyone can view without logging in
- [ ] "Try Mira" CTA button on the shared card page

**Priority**: 🟠 P1 · **Effort**: M · **Value**: 9/10

---

### Story E3-2 · Shareable referral link
**As a** happy user  
**I want** a personal referral link  
**So that** when I share it and a friend signs up, we both get a small reward (or just recognition)

**Acceptance criteria**
- [ ] Each user has a unique `ref=<code>` parameter
- [ ] Sign-ups via referral link are tracked in Supabase
- [ ] Referrer sees a count "3 friends joined via your link"
- [ ] Phase 1: tracking only — no reward needed yet

**Priority**: 🟡 P2 · **Effort**: S · **Value**: 7/10

---

## E4 · Email Capture & CRM Foundation

> **Why P1**: Without email, you have no way to re-engage users who leave. Email is your retention lifeline before you have an app.

---

### Story E4-1 · Email capture at session end
**As a** product owner  
**I want** to capture the user's email before they leave  
**So that** I can send them their saved items and bring them back

**Acceptance criteria**
- [ ] After first conversation ends, show: "Save your picks — enter your email and we'll send your Mira session"
- [ ] Email stored in `users` table (add `email` column)
- [ ] Opt-in checkbox for "Send me style tips from Mira" (GDPR compliant)
- [ ] Non-blocking: user can dismiss without entering email

**Priority**: 🟠 P1 · **Effort**: S · **Value**: 9/10

---

### Story E4-2 · "Your picks" summary email
**As a** user who gave my email  
**I want** to receive a summary of my Mira session  
**So that** I can revisit the products I was interested in later

**Acceptance criteria**
- [ ] Email sent within 5 minutes of session end
- [ ] Shows: saved products with image + name + price + affiliate link
- [ ] "Chat with Mira again" CTA button
- [ ] Uses Resend or SendGrid (free tier)
- [ ] Unsubscribe link present (CAN-SPAM/GDPR)

**Priority**: 🟠 P1 · **Effort**: M · **Value**: 9/10

---

### Story E4-3 · Restock & price drop alert email
**As a** user who saved a product  
**I want** to be notified if the price drops  
**So that** I don't miss a deal on something I already wanted

**Acceptance criteria**
- [ ] Nightly job checks prices for all products in user_history (would_buy action)
- [ ] If price drops ≥ 10 %, send email: "Good news — [Product] just dropped to $X"
- [ ] Deep link back to Mira session with that product highlighted
- [ ] Max 1 price alert per product per user per week

**Priority**: 🟢 P3 · **Effort**: M · **Value**: 8/10

---

---

# 🟡 P2 — Monetise

---

## E5 · Amazon PA-API Unlock

> **Why critical**: PA-API = access to 300 M products, real-time pricing, and reliable images. SiteStripe links expire. PA-API links don't.

---

### Story E5-1 · Drive 3 qualifying Amazon sales
**As a** founder  
**I want** to generate 3 legitimate Amazon sales through affiliate links  
**So that** I can apply for PA-API access (Amazon's requirement)

**Acceptance criteria**
- [ ] 3 distinct customers (not the founder) click "Buy →" and complete a purchase
- [ ] Amazon Associates dashboard shows 3 qualifying sales
- [ ] PA-API application submitted within 24 h of 3rd sale

**Priority**: 🟡 P2 · **Effort**: XL (sales effort, not eng) · **Value**: 10/10

---

### Story E5-2 · PA-API product search integration
**As a** developer  
**I want** to search Amazon's live catalog via PA-API  
**So that** Mira can recommend any of 300 M products, not just the 200 in our Supabase

**Acceptance criteria**
- [ ] `amazon_source.py` implements ProductSource protocol using PA-API
- [ ] Search by keyword + category + price range
- [ ] Returns: ASIN, name, image_url, price, affiliate_url (with associate tag)
- [ ] Results cached in Supabase products table (soft-upsert) to avoid redundant API calls
- [ ] Fallback to curated Supabase catalog if PA-API unavailable

**Priority**: 🟡 P2 · **Effort**: M · **Value**: 10/10

---

### Story E5-3 · Dynamic affiliate URL generation
**As a** developer  
**I want** affiliate URLs generated programmatically per product + user  
**So that** we can track which user drove which sale and personalise commission splits later

**Acceptance criteria**
- [ ] All affiliate URLs include associate tag from env var
- [ ] URL format: `https://www.amazon.com/dp/{ASIN}?tag={TAG}&linkCode=...`
- [ ] Custom tracking ID per session embedded in URL for analytics
- [ ] Old hardcoded SiteStripe links migrated to this format

**Priority**: 🟡 P2 · **Effort**: S · **Value**: 8/10

---

## E8 · Analytics Dashboard

---

### Story E8-1 · Product performance report
**As a** founder  
**I want** to see which products get the most saves and buy-clicks  
**So that** I know what to add more of to the catalog

**Acceptance criteria**
- [ ] Dashboard page (password-protected) shows:
  - Top 10 products by save rate (would_buy / shown)
  - Top 10 products by buy-click rate
  - Bottom 10 (low engagement — candidates for removal)
- [ ] Filterable by date range (last 7 / 30 / 90 days)
- [ ] Built on Supabase queries — no new infra needed

**Priority**: 🟡 P2 · **Effort**: M · **Value**: 8/10

---

### Story E8-2 · Session funnel metrics
**As a** founder  
**I want** to see the user journey from session start to purchase click  
**So that** I know where users drop off

**Acceptance criteria**
- [ ] Funnel: Sessions started → Products shown → Products saved → Buy clicks
- [ ] Conversion rate at each step shown as %
- [ ] Average session length (turns / time)
- [ ] New vs returning user breakdown

**Priority**: 🟡 P2 · **Effort**: M · **Value**: 8/10

---

### Story E8-3 · Revenue estimate tracker
**As a** founder  
**I want** to see estimated affiliate earnings  
**So that** I can report progress to investors and set pricing targets

**Acceptance criteria**
- [ ] Estimated revenue = buy_click events × average Amazon affiliate rate (3–8 % by category)
- [ ] Shown as: "Estimated this month: $X — actual confirmed in Associates dashboard"
- [ ] 30-day rolling chart

**Priority**: 🟡 P2 · **Effort**: S · **Value**: 7/10

---

---

# 🟢 P3 — Retain

---

## E10 · User Profile & Style Memory

---

### Story E10-1 · "Your Mira" profile page
**As a** returning user  
**I want** to see my style history in one place  
**So that** I feel like Mira genuinely knows me

**Acceptance criteria**
- [ ] Page shows: name, member since, total sessions, saved items, buy-clicked items
- [ ] "Your style profile": inferred vibes (casual, chic, minimal etc.) based on saved items
- [ ] Edit: budget preference, gender, sizes (optional)
- [ ] "Start a new session" CTA

**Priority**: 🟢 P3 · **Effort**: M · **Value**: 8/10

---

### Story E10-2 · Occasion calendar
**As a** user planning ahead  
**I want** to tell Mira about upcoming events  
**So that** she can proactively suggest outfits before I need them

**Acceptance criteria**
- [ ] User can add occasions: name + date + dress code (smart casual / formal / casual)
- [ ] Stored in Supabase `user_occasions` table
- [ ] 7 days before occasion: Mira-themed reminder email with outfit suggestions
- [ ] In session, Mira references upcoming occasions: "You've got that wedding in 10 days — want to pick something today?"

**Priority**: 🟢 P3 · **Effort**: M · **Value**: 8/10

---

## E11 · Outfit Completion Engine

> **Why**: Increases average basket from 1 item to 3–4 items. Biggest single revenue lever.

---

### Story E11-1 · "Complete the look" recommendation
**As a** shopper who saved a dress  
**I want** Mira to suggest shoes and a bag to go with it  
**So that** I can buy a complete outfit in one session

**Acceptance criteria**
- [ ] When user saves an item, Mira proactively offers: "Want me to find shoes and a bag to complete this look?"
- [ ] Completion items filtered by: complementary category, similar price range, compatible style tags
- [ ] Works for any anchor category: dress → shoes + bag; tops → bottoms + shoes; etc.
- [ ] Mira explains the styling logic for each addition

**Priority**: 🟢 P3 · **Effort**: M · **Value**: 9/10

---

### Story E11-2 · Outfit bundle save
**As a** shopper  
**I want** to save a complete outfit (not just individual items)  
**So that** I can come back and buy everything together

**Acceptance criteria**
- [ ] "Save outfit" button appears when 2+ compatible items are shown together
- [ ] Outfit stored in `user_outfits` table with name (e.g. "Date Night Look")
- [ ] Profile page shows saved outfits with total price
- [ ] Share button on outfit (drives E3 viral loop)

**Priority**: 🟢 P3 · **Effort**: M · **Value**: 8/10

---

---

# 🔵 P4 — Scale

---

## E12 · White-Label Mira for Brands

---

### Story E12-1 · Brand skin configuration
**As a** brand partner  
**I want** to configure Mira with my brand name, colors, and catalog  
**So that** I can offer an AI stylist to my customers without building one

**Acceptance criteria**
- [ ] Brand config: `name`, `persona_prompt`, `primary_color`, `logo_url`, `catalog_source`
- [ ] Stored in `brands` table; loaded at session start based on subdomain or API key
- [ ] Catalog filtered to brand's own products only
- [ ] Custom greeting: "Hi, I'm [Brand] Style Assistant"

**Priority**: 🔵 P4 · **Effort**: L · **Value**: 9/10

---

## E13 · Brand Sponsorship & Promoted Products

---

### Story E13-1 · Promoted placement in catalog
**As a** brand  
**I want** my products to appear higher in Mira's recommendations  
**So that** I can drive more visibility for new launches or clearance

**Acceptance criteria**
- [ ] Products table has `promoted_until` timestamptz and `promoted_weight` float
- [ ] `search_products()` boosts promoted products in ranking (not forced — only if relevant to query)
- [ ] Mira's grounding prompt notes: "★ = brand partner product — recommend if genuinely fitting"
- [ ] Promotion disclosed in UI: small "Sponsored" label on card

**Priority**: 🔵 P4 · **Effort**: S · **Value**: 8/10

---

---

# Backlog Summary Table

| Epic | Stories | Priority | Total Effort | Value |
|------|---------|----------|--------------|-------|
| E1 Catalog Expansion | 3 | 🔴 P0 | M–L | 10 |
| E2 Mobile / PWA | 3 | 🔴 P0 | S | 9 |
| E6 Error States | 3 | 🔴 P0 | S | 8 |
| E7 Rate Limiting | 2 | 🔴 P0 | XS | 8 |
| E9 Privacy & Legal | 2 | 🔴 P0 | S | 8 |
| E3 Viral Sharing | 2 | 🟠 P1 | M | 9 |
| E4 Email & CRM | 3 | 🟠 P1 | M | 9 |
| E5 Amazon PA-API | 3 | 🟡 P2 | M | 10 |
| E8 Analytics | 3 | 🟡 P2 | M | 8 |
| E10 User Profile | 2 | 🟢 P3 | M | 8 |
| E11 Outfit Engine | 2 | 🟢 P3 | M | 9 |
| E12 White-Label | 1 | 🔵 P4 | L | 9 |
| E13 Sponsorships | 1 | 🔵 P4 | S | 8 |

**Total stories: 30 · Estimated total effort (solo dev): ~14 weeks**

---

## The Immovable First Action

Before any engineering: **manually add 50 products to the catalog this week**.  
No sprint, no story — just open Amazon, SiteStripe 50 items across 6 categories, run `migrate_products.py`.  
Every other story depends on having a real catalog. That's the one thing no amount of code can substitute for.
