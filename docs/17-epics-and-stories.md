# Mira AI Stylist — Epics & User Stories

_Last updated: July 2026. India-first MVP strategy, affiliate + subscription revenue model._

---

## Priority tiers

| Tag | Meaning |
|-----|---------|
| 🔴 P0 Gate | Blocking. Must ship before any real user touches the app. |
| 🟠 P1 Launch | Required to call this a real, shareable product. |
| 🟡 P2 Monetise | Turns traffic into revenue. |
| 🟢 P3 Retain | Keeps users coming back week after week. |
| 🔵 P4 Scale | Platform plays, B2B, white-label. |

**Effort** (eng-days, solo developer):
`XS` < 1d · `S` 1–2d · `M` 3–5d · `L` 1–2w · `XL` 2–4w

**Status**: ✅ Done · 🔄 In progress · ⬜ Not started

---

## Sprint roadmap (India MVP)

| Sprint | Theme | Epics | Status |
|--------|-------|-------|--------|
| S1 | Foundation | E1 Voice bridge · E2 Auth · E3 Onboarding | ✅ Done |
| S2 | Personalisation | E4 Recommendations · E5 Session Management | ✅ Done |
| S3 | India Catalogue | E6 VCommission Feed · E7 Myntra/Ajio affiliate | ⬜ |
| S4 | Growth | E8 Pinterest OAuth · E9 First Look drops | ⬜ |
| S5 | Money | E10 Subscription paywall · E11 Analytics | ⬜ |
| S6 | Mobile & Retention | E12 PWA · E13 Email CRM · E14 Outfit Engine | ⬜ |
| S7 | Scale | E15 White-label · E16 Brand sponsorships | ⬜ |

---

---

# ✅ COMPLETED — Foundation & Core Engine

---

## E1 · Voice AI Bridge

**Goal**: Real-time voice conversation with Mira powered by Gemini Live, running on Fly.io.

| Story | Description | Status |
|-------|-------------|--------|
| E1-1 | WebSocket bridge (live_server.py) with Gemini Live audio | ✅ |
| E1-2 | Text / silent mode — full chat UI, no mic needed | ✅ |
| E1-3 | Fly.io deployment with nginx WebSocket proxy | ✅ |
| E1-4 | Hot reload in dev — watchmedo auto-restarts on .py save | ✅ |
| E1-5 | Health check handler — nginx pings don't crash WS server | ✅ |
| E1-6 | Idle timeout 3 min — auto-closes Gemini session to cap cost | ✅ |
| E1-7 | Hard session cap 20 min — absolute cost guardrail | ✅ |
| E1-8 | Gemini session auto-reconnect — transparent to user | ✅ |

---

## E2 · Auth & Identity

**Goal**: Users sign in with Google/GitHub, have a persistent identity, and can sign out.

| Story | Description | Status |
|-------|-------------|--------|
| E2-1 | Supabase Google OAuth (implicit flow) | ✅ |
| E2-2 | GitHub OAuth | ✅ |
| E2-3 | User menu with avatar, name, email, sign-out | ✅ |
| E2-4 | Session idle warning modal (countdown + stay/leave) | ✅ |
| E2-5 | Fly.io Site URL + redirect URL config in Supabase | ✅ |

---

## E3 · Onboarding & Style Profile

**Goal**: New users answer 4 quick questions so Mira personalises from the very first message.

| Story | Description | Status |
|-------|-------------|--------|
| E3-1 | 4-step quiz: style vibe → shopping focus → sizes → budget | ✅ |
| E3-2 | Prefs stored in Supabase `user_preferences` table | ✅ |
| E3-3 | Prefs sent to server on WS init and baked into Mira's grounding prompt | ✅ |
| E3-4 | Skip option — user can bypass and tell Mira verbally | ✅ |
| E3-5 | Schema migration for old column names (migrate_user_preferences.sql) | ✅ |

---

## E4 · Recommendations & Product Engine

**Goal**: Mira shows the right products at the right time; top picks are personalised on load.

| Story | Description | Status |
|-------|-------------|--------|
| E4-1 | 1,136-product catalog in Supabase, served from in-memory cache | ✅ |
| E4-2 | 40-product curated spotlight (5 per category) for grounding | ✅ |
| E4-3 | Top picks push on session connect (10 products, before Mira speaks) | ✅ |
| E4-4 | Personalised top picks — scored by user's budget + shopping focus | ✅ |
| E4-5 | `show_more` pagination — 10 more from full 1,136-product catalog | ✅ |
| E4-6 | Saved products restored on reconnect (`restore_loved`) | ✅ |
| E4-7 | Taste profile from saved products — fed into Mira's grounding prompt | ✅ |
| E4-8 | `_match_products` — token-match Mira's speech to push product cards | ✅ |
| E4-9 | Save / unlike products — persisted to `user_history` in Supabase | ✅ |

---

## E5 · Session Management & Cost Controls

| Story | Description | Status |
|-------|-------------|--------|
| E5-1 | Watchdog coroutine — closes idle sessions (3 min default) | ✅ |
| E5-2 | Cost logging per session (tokens in/out, duration, estimated $) | ✅ |
| E5-3 | `dev.sh` — one command starts both servers with hot reload | ✅ |
| E5-4 | `deploy.sh` — one command deploys to Fly.io with secrets | ✅ |

---

---

# 🔴 P0 — Gate (must ship before real users)

---

## E6 · Error States & Reliability

> Right now a dropped connection = blank screen. That's a trust-killer for a first-time user.

### E6-1 · Friendly offline state
**As a** user whose server is unreachable  
**I want** a helpful message instead of a blank screen  
**So that** I don't assume the app is broken and leave forever

**Acceptance criteria**
- [ ] WebSocket failure shows: "Mira is taking a quick break — try again in a moment"
- [ ] Retry button attempts reconnect (up to 3 times)
- [ ] After 3 failures: "Something's wrong on our end. We'll be back soon."
- [ ] No raw error text or stack traces visible

**Priority**: 🔴 P0 · **Effort**: XS · **Status**: ⬜

---

### E6-2 · Rate limiting — per-IP session cap
**As a** platform operator  
**I want** to cap WebSocket connections per IP  
**So that** one user or bot can't exhaust the Gemini API quota for everyone

**Acceptance criteria**
- [ ] Max 3 concurrent sessions per IP
- [ ] Max 10 session starts per IP per hour
- [ ] Excess gets: `{"type":"error","message":"Too many sessions — try again shortly"}`
- [ ] Limits configurable via env vars

**Priority**: 🔴 P0 · **Effort**: XS · **Status**: ⬜

---

### E6-3 · Privacy policy & data disclosure
**As a** user  
**I want** to know what data Mira stores  
**So that** I can make an informed choice, and Mira complies with India's DPDP Act 2023

**Acceptance criteria**
- [ ] Privacy policy page exists at `/privacy`
- [ ] Covers: user_id, name, product interactions, retention period, third-party sharing (Gemini, Supabase)
- [ ] Consent checkbox on sign-up
- [ ] Link in footer

**Priority**: 🔴 P0 · **Effort**: S · **Status**: ⬜

---

### E6-4 · Right-to-delete
**As a** user  
**I want** to delete my account and all my data  
**So that** I can exercise my rights under DPDP / GDPR

**Acceptance criteria**
- [ ] "Delete account" in user menu → confirmation dialog → deletes all rows by user_id
- [ ] FK cascade already in schema — verify it works end-to-end
- [ ] Confirmation email (or in-app toast)

**Priority**: 🔴 P0 · **Effort**: S · **Status**: ⬜

---

---

# 🟠 P1 — Launch (India MVP)

---

## E7 · VCommission Affiliate Feed (India)

> **Why first for India**: VCommission covers Myntra, Ajio, Amazon India, Nykaa Fashion in one integration. This replaces the synthetic US catalog with real Indian products and real affiliate revenue.

### E7-1 · VCommission feed importer
**As a** developer  
**I want** to pull a live product feed from VCommission  
**So that** Mira recommends real Indian fashion products with working affiliate links

**Acceptance criteria**
- [ ] Script pulls CSV/API feed from VCommission for: Myntra, Ajio, Amazon Fashion India
- [ ] Maps fields to Supabase products schema (name, category, color, price, image_url, affiliate_url)
- [ ] Deduplicates by URL/SKU before inserting
- [ ] Runs daily via cron (Fly.io cron job or GitHub Actions)
- [ ] Only imports products with valid image_url and price
- [ ] Covers all target categories: tops, bottoms, dresses, outerwear, shoes, bags, accessories

**Priority**: 🟠 P1 · **Effort**: M · **Status**: ⬜

---

### E7-2 · India price currency (₹)
**As a** Indian user  
**I want** to see prices in rupees  
**So that** I don't have to mentally convert from dollars

**Acceptance criteria**
- [ ] Products table has `currency` column (default: INR for new feed imports)
- [ ] ProductCard and FeaturedProduct render ₹ symbol when currency = INR
- [ ] Grounding prompt tells Mira to say "rupees" not "dollars" for INR products

**Priority**: 🟠 P1 · **Effort**: XS · **Status**: ⬜

---

### E7-3 · Nike / Adidas India direct affiliate
**As a** business owner  
**I want** direct affiliate agreements with Nike and Adidas India  
**So that** premium sportswear — core to the 22–35 corporate demo — is in the catalog

**Acceptance criteria**
- [ ] Applied to Nike India affiliate program (via their website or VCommission)
- [ ] Applied to Adidas India affiliate program
- [ ] Products imported with direct brand affiliate URLs (not Google Shopping fallback)
- [ ] At least 50 Nike + 50 Adidas products in catalog

**Priority**: 🟠 P1 · **Effort**: S (outreach, not eng) · **Status**: ⬜

---

## E8 · Pinterest OAuth — Style Board Analysis

> **Why**: Pinterest boards are "I want this" intent (stronger than Instagram likes). User connects once; Mira knows their aesthetic immediately. 2-day build.

### E8-1 · Pinterest OAuth connect
**As a** user during onboarding  
**I want** to connect my Pinterest account  
**So that** Mira can learn my style from boards I've already curated

**Acceptance criteria**
- [ ] "Connect Pinterest" button on onboarding step 2 (after style quiz)
- [ ] Pinterest OAuth v5 flow: user authorises read_pins, read_boards
- [ ] Access token stored encrypted in `user_integrations` table
- [ ] Graceful skip if user doesn't have Pinterest

**Priority**: 🟠 P1 · **Effort**: S · **Status**: ⬜

---

### E8-2 · Board & pin analysis
**As a** developer  
**I want** to analyse a user's Pinterest boards for style signals  
**So that** Mira's recommendation profile is enriched before the first conversation

**Acceptance criteria**
- [ ] Fetch user's boards and top 50 pins via Pinterest API v5
- [ ] For each pin image: call Gemini Vision to extract (category, color palette, style vibe, occasion)
- [ ] Aggregate into a style summary: top 3 categories, dominant colors, primary vibe
- [ ] Store summary in `user_preferences.pinterest_style_summary` (text field)
- [ ] Summary injected into Mira's grounding prompt: "From their Pinterest: loves minimal dresses, navy + beige, office-to-evening occasions"

**Priority**: 🟠 P1 · **Effort**: M · **Status**: ⬜

---

### E8-3 · Inspo link drop (no Pinterest account needed)
**As a** user without Pinterest  
**I want** to paste an Instagram/Pinterest post URL  
**So that** Mira can analyse the outfit and understand my style

**Acceptance criteria**
- [ ] Input field in onboarding: "Drop an inspo link (Instagram, Pinterest, any image URL)"
- [ ] Gemini Vision analyses the image from the URL
- [ ] Extracted style signals added to user profile
- [ ] Works for public Instagram posts and direct image URLs

**Priority**: 🟠 P1 · **Effort**: S · **Status**: ⬜

---

## E9 · "First Look" — New Launch Feed

> **The moat**: No one surfaces new Indian fashion drops through an AI stylist. This is the reason to subscribe.

### E9-1 · New arrivals ingestion
**As a** product owner  
**I want** to ingest new product launches from Myntra/Ajio daily  
**So that** Mira's catalog always has the freshest drops

**Acceptance criteria**
- [ ] VCommission or Myntra affiliate feed filtered for `date_added` within last 7 days
- [ ] Products tagged `is_new_launch = true` for 14 days after import
- [ ] Mira's grounding prompt notes: "★ NEW = launched this week — mention as fresh finds"

**Priority**: 🟠 P1 · **Effort**: S · **Status**: ⬜

---

### E9-2 · "First Look" weekly email
**As a** subscriber  
**I want** a weekly email of new drops curated to my style  
**So that** I see fresh launches before they go viral, without opening the app

**Acceptance criteria**
- [ ] Every Monday 9 AM IST: email sent to all Pro subscribers
- [ ] Shows 6–8 new arrivals matched to user's style profile and budget
- [ ] Subject line: "Mira's First Look — this week's drops, picked for you"
- [ ] "Chat with Mira" CTA deep-links to a pre-loaded session about these products
- [ ] Sent via Resend (free up to 3,000/month)

**Priority**: 🟠 P1 · **Effort**: M · **Status**: ⬜

---

### E9-3 · In-app "New this week" shelf
**As a** returning user  
**I want** to see what dropped since my last visit  
**So that** every session feels fresh and worth opening

**Acceptance criteria**
- [ ] "New this week ✦" shelf appears above the standard product grid on the home screen
- [ ] Shows last 7 days of new arrivals filtered by user's budget range
- [ ] Shelf is collapsible; hidden if user has no prefs set (fallback to standard top picks)

**Priority**: 🟠 P1 · **Effort**: S · **Status**: ⬜

---

---

# 🟡 P2 — Monetise

---

## E10 · Subscription Paywall

> **Revenue model**: Affiliate commission (free) + Pro subscription (₹299/month). Free tier is the funnel; Pro is the moat.

### E10-1 · Free vs Pro feature split
**As a** product owner  
**I want** a clear free/paid split  
**So that** free users get genuine value but Pro is an obvious upgrade

| Feature | Free | Pro (₹299/mo) |
|---------|------|--------------|
| Conversations/month | 3 | Unlimited |
| Top picks on load | Generic | Personalised |
| First Look email | — | Weekly |
| Pinterest sync | — | ✓ |
| Outfit builder | — | ✓ |
| New arrivals shelf | — | ✓ |

**Acceptance criteria**
- [ ] `user_subscriptions` table: user_id, plan (free/pro), started_at, expires_at
- [ ] Conversation counter incremented per session; block at 3 for free tier
- [ ] Paywall modal shows value prop + "Start Pro — ₹299/month"
- [ ] Free tier still earns affiliate commission (never block the buy flow)

**Priority**: 🟡 P2 · **Effort**: M · **Status**: ⬜

---

### E10-2 · Razorpay payment integration
**As a** user  
**I want** to pay for Pro via UPI, card, or net banking  
**So that** I can upgrade without friction (India-native payment methods)

**Acceptance criteria**
- [ ] Razorpay Subscription API integration (handles recurring ₹299/month)
- [ ] Payment widget embedded in paywall modal
- [ ] Webhook updates `user_subscriptions` table on success/failure/renewal
- [ ] Receipt email via Resend
- [ ] Cancel anytime — no dark patterns

**Priority**: 🟡 P2 · **Effort**: M · **Status**: ⬜

---

## E11 · Analytics & Revenue Tracking

### E11-1 · Affiliate performance dashboard
**As a** founder  
**I want** to see which products drive saves and buy-clicks  
**So that** I know what to source more of

**Acceptance criteria**
- [ ] Password-protected `/admin` page
- [ ] Top 10 products by: shown → saved conversion, saved → buy-click conversion
- [ ] Bottom 10 (low engagement → remove from catalog)
- [ ] Filter by date range and platform (Myntra / Ajio / Amazon)

**Priority**: 🟡 P2 · **Effort**: M · **Status**: ⬜

---

### E11-2 · Session funnel & revenue estimate
**As a** founder  
**I want** to see the conversion funnel and estimated earnings  
**So that** I can report progress and set targets

**Acceptance criteria**
- [ ] Funnel: Sessions → Products shown → Saves → Buy-clicks
- [ ] Estimated revenue = buy_clicks × avg commission rate by platform
- [ ] Free vs Pro user breakdown
- [ ] 30-day rolling chart

**Priority**: 🟡 P2 · **Effort**: M · **Status**: ⬜

---

### E11-3 · Influencer tracking — "Mira noticed [Influencer] wore this"
**As a** product owner  
**I want** to track which Indian fashion influencers wear products in our catalog  
**So that** Mira can surface "as seen on [Komal Pandey]" context

**Acceptance criteria**
- [ ] Curated list of 20–30 Indian fashion influencers (Instagram handles)
- [ ] Weekly scrape of their public posts (manual tagging initially, or with Meta Graph API)
- [ ] Products table has `influencer_tag` column linking to influencer handle
- [ ] In grounding prompt: "★ = seen on [influencer] — mention this if relevant"
- [ ] ProductCard shows small "As seen on @handle" label for tagged products

**Priority**: 🟡 P2 · **Effort**: M · **Status**: ⬜

---

---

# 🟢 P3 — Retain

---

## E12 · Mobile PWA

> 73% of fashion shopping in India is on mobile. If it doesn't work on a phone, it doesn't exist.

### E12-1 · Responsive chat layout
**As a** mobile user  
**I want** the chat UI to fill my phone screen without horizontal scroll  
**So that** I can use Mira on my phone

**Acceptance criteria**
- [ ] No horizontal scroll at 320px–430px viewport width
- [ ] Chat input stays above keyboard using `env(safe-area-inset-bottom)`
- [ ] Product cards readable at 375px
- [ ] Tested on Chrome/Safari iOS and Chrome Android

**Priority**: 🟢 P3 · **Effort**: S · **Status**: ⬜

---

### E12-2 · PWA install + offline shell
**As a** returning user  
**I want** to add Mira to my home screen  
**So that** I open her like a native app

**Acceptance criteria**
- [ ] `manifest.json` with name, icons (192 + 512px), theme_color, display: standalone
- [ ] Service worker caches app shell
- [ ] Offline shows: "Mira needs a connection — tap to retry"
- [ ] Lighthouse PWA score ≥ 80

**Priority**: 🟢 P3 · **Effort**: S · **Status**: ⬜

---

### E12-3 · Default to text mode on mobile
**As a** mobile user in public  
**I want** text mode to be default on phones  
**So that** I can use Mira without mic permissions or speaking aloud

**Acceptance criteria**
- [ ] Detect mobile (screen width < 768px) → default textMode = true
- [ ] Voice mode accessible via toggle
- [ ] Preference saved to localStorage

**Priority**: 🟢 P3 · **Effort**: XS · **Status**: ⬜

---

## E13 · Email CRM & Re-engagement

### E13-1 · Session summary email
**As a** user who ended a session  
**I want** an email with my saved products  
**So that** I can come back and buy when I'm ready

**Acceptance criteria**
- [ ] Email sent within 5 min of session end (if user has email on record)
- [ ] Shows saved items: image + name + price + affiliate link
- [ ] "Chat with Mira again" CTA
- [ ] Unsubscribe link (CAN-SPAM compliant)
- [ ] Sent via Resend free tier

**Priority**: 🟢 P3 · **Effort**: M · **Status**: ⬜

---

### E13-2 · Occasion reminder
**As a** user who added a wedding to Mira  
**I want** a reminder email 7 days before  
**So that** I don't forget to buy my outfit in time

**Acceptance criteria**
- [ ] `user_occasions` table: user_id, event_name, event_date, dress_code
- [ ] Mira can add occasions mid-conversation: "I'll remind you 7 days before your event"
- [ ] 7-day-before email: outfit suggestions matched to dress_code + user budget
- [ ] "Ask Mira to style me" deep-link CTA

**Priority**: 🟢 P3 · **Effort**: M · **Status**: ⬜

---

## E14 · Outfit Completion Engine

> Increases average session basket from 1 item to 3–4 items. Biggest single revenue lever.

### E14-1 · "Complete the look" suggestion
**As a** shopper who saved a dress  
**I want** Mira to suggest matching shoes and a bag  
**So that** I leave with a complete outfit, not just one piece

**Acceptance criteria**
- [ ] When user saves an item, Mira offers: "Want me to find shoes to go with this?"
- [ ] Completion items filtered by: complementary category, similar price tier, compatible style
- [ ] Works for any anchor: dress → shoes + bag; top → bottoms + shoes; etc.
- [ ] Mira explains why each piece works ("the ankle boots balance the midi length")

**Priority**: 🟢 P3 · **Effort**: M · **Status**: ⬜

---

### E14-2 · Outfit bundle save
**As a** user  
**I want** to save a full outfit, not just individual items  
**So that** I can come back and buy everything at once

**Acceptance criteria**
- [ ] "Save outfit" button when 2+ items are shown together
- [ ] `user_outfits` table: id, user_id, name, product_ids[], total_price
- [ ] Profile page shows saved outfits with total price
- [ ] Share button on outfit (drives viral loop)

**Priority**: 🟢 P3 · **Effort**: M · **Status**: ⬜

---

---

# 🔵 P4 — Scale

---

## E15 · White-Label Mira for Indian Brands

### E15-1 · Brand skin & catalog isolation
**As a** fashion brand (e.g. Rare Rabbit, Bewakoof, W for Woman)  
**I want** to offer Mira with my brand name and catalog  
**So that** my customers get an AI stylist without me building one

**Acceptance criteria**
- [ ] `brands` table: name, persona_prompt, primary_color, logo_url, catalog_source
- [ ] Loaded at session start based on subdomain or API key
- [ ] Catalog filtered to brand's products only
- [ ] Custom greeting: "Hi, I'm [Brand] Style Assistant"
- [ ] Pricing: ₹15,000–50,000/month brand SaaS fee

**Priority**: 🔵 P4 · **Effort**: L · **Status**: ⬜

---

## E16 · Promoted Placements & Brand Partnerships

### E16-1 · Sponsored product placement
**As a** brand partner  
**I want** my new collection to appear first in Mira's recommendations  
**So that** I get visibility for a launch without a traditional ad campaign

**Acceptance criteria**
- [ ] Products table has `promoted_until` timestamptz and `promoted_weight` float
- [ ] Promoted products scored higher in spotlight selection (not forced — only if relevant)
- [ ] "Sponsored" label on product card (disclosed clearly)
- [ ] Mira's prompt: "★ = brand partner product — recommend only if genuinely fitting"
- [ ] Pricing: ₹50,000–2,00,000/month per promoted slot

**Priority**: 🔵 P4 · **Effort**: S · **Status**: ⬜

---

---

# Backlog summary

| Epic | Stories | Priority | Effort | Status |
|------|---------|----------|--------|--------|
| E1 Voice AI Bridge | 8 | ✅ Done | — | ✅ |
| E2 Auth & Identity | 5 | ✅ Done | — | ✅ |
| E3 Onboarding & Style Profile | 5 | ✅ Done | — | ✅ |
| E4 Recommendations | 9 | ✅ Done | — | ✅ |
| E5 Session & Cost Controls | 4 | ✅ Done | — | ✅ |
| E6 Error States & Privacy | 4 | ✅ Done | — | ✅ |
| E7 Chat-First UI & Mode Switching | 5 | ✅ Done | — | ✅ |
| E8 Cart & Try On | 3 | 🔴 P0 | S | ⬜ |
| E9 AI Product Videos | 2 | 🔴 P0 | S | ⬜ |
| E10 VCommission India Feed | 4 | 🟠 P1 | M | ⬜ |
| E11 Amazon PA-API + Reviews | 3 | 🟠 P1 | M | ⬜ |
| E12 Network Quality (Safari fix) | 1 | 🟠 P1 | XS | ⬜ |
| E13 EventBrief UI Redesign | 2 | 🟡 P2 | S | ⬜ |
| E14 Subscription Paywall | 2 | 🟡 P2 | M | ⬜ |
| E15 Analytics & Influencer | 3 | 🟡 P2 | M | ⬜ |
| E16 Mobile PWA | 3 | 🟢 P3 | S | ⬜ |
| E17 Email CRM | 2 | 🟢 P3 | M | ⬜ |
| E18 Outfit Completion Engine | 2 | 🟢 P3 | M | ⬜ |
| E19 Pinterest OAuth | 3 | 🟢 P3 | M | ⬜ |
| E20 Rewards / Loyalty | 2 | 🟢 P3 | M | ⬜ |
| E21 White-Label | 1 | 🔵 P4 | L | ⬜ |
| E22 Brand Sponsorships | 1 | 🔵 P4 | S | ⬜ |
| E23 Meta AI Glasses | 1 | 🔵 P4 | XL | ⬜ |

**Total remaining stories: ~44 · Estimated effort (solo dev): ~13 weeks**

---

## E8 · Cart & Try On

> **Why P0**: The shop-in-India mental model — browse 3 → shortlist → fitting room → buy. Currently users can save products but there's no "fitting room" moment.

### Story E8-1 · Cart panel (fitting room)
**As a** shopper  
**I want** to see my shortlisted items side-by-side in a dedicated view  
**So that** I can compare them and decide what to try on

**Acceptance criteria**
- [ ] Max 3 items in cart; prompt to remove one before adding a 4th
- [ ] Cart panel shows bigger cards (image, name, price, reason saved)
- [ ] "Remove" per item, "Clear all" button
- [ ] Accessible from a persistent cart icon in the header showing item count

**Priority**: 🔴 P0 · **Effort**: S · **Value**: 9/10

---

### Story E8-2 · Try On button (MVP: fullscreen viewer)
**As a** shopper  
**I want** to see a product fullscreen before buying  
**So that** I can inspect it closely without leaving the app

**Acceptance criteria**
- [ ] "Try On" button on each cart item
- [ ] Opens fullscreen image viewer with product details overlay
- [ ] "Buy →" affiliate link visible in viewer
- [ ] Falls back gracefully if no image available

**Priority**: 🔴 P0 · **Effort**: XS · **Value**: 8/10

---

### Story E8-3 · Try On V2 (AI product video)
**As a** shopper  
**I want** to see the product in motion on a model  
**So that** I can judge fit and drape better than a static image

**Acceptance criteria**
- [ ] Runway or Kling AI API generates a 5s showcase video per product
- [ ] Video URL cached in `products.video_url` column (one-time generation)
- [ ] Video plays in the fullscreen viewer when available
- [ ] Fallback to static image if no video generated yet
- [ ] Cost target: under ₹400 for first 50 products

**Priority**: 🔴 P0 (once API key obtained) · **Effort**: S · **Value**: 9/10

---

## E9 · AI Product Videos

### Story E9-1 · Video generation pipeline
**As a** developer  
**I want** a script that generates showcase videos for catalog products  
**So that** the Try On experience has motion content from day one

**Acceptance criteria**
- [ ] Script reads products without `video_url` from Supabase
- [ ] Sends `image_url` + prompt to Runway Gen-4 or Kling AI
- [ ] Stores returned video URL in `products.video_url`
- [ ] Runs idempotently (skip products that already have a video)
- [ ] Rate-limited to avoid API quota exhaustion

**Priority**: 🔴 P0 · **Effort**: S · **Value**: 9/10

---

### Story E9-2 · `video_url` column in products schema
**As a** developer  
**I want** a `video_url` column on the `products` table  
**So that** generated videos persist and aren't regenerated on every run

**Acceptance criteria**
- [ ] `alter table products add column if not exists video_url text;` run in Supabase
- [ ] `product_source.py` returns `video_url` in product dicts
- [ ] Frontend `ProductCard` renders video if `video_url` present

**Priority**: 🔴 P0 · **Effort**: XS · **Value**: 8/10

---

## E10 · VCommission India Feed

### Story E10-1 · Publisher signup (user action)
**As a** founder  
**I want** a VCommission publisher account  
**So that** I can access affiliate feeds for Myntra, Ajio, SNITCH, Bewakoof, Cord

**Acceptance criteria**
- [ ] Signed up at vcommission.com with publisher ID obtained
- [ ] Approved for: Myntra, Ajio, Amazon India, SNITCH, Bewakoof
- [ ] API credentials stored in `prototype/.env` as `VCOMMISSION_API_KEY`

**Priority**: 🟠 P1 · **Effort**: XS (user action) · **Value**: 10/10

---

### Story E10-2 · Feed importer script
**As a** developer  
**I want** a daily import script that pulls VCommission product feeds  
**So that** the catalog grows automatically with real Indian affiliate products

**Acceptance criteria**
- [ ] Fetches product feed (XML/CSV) from VCommission API
- [ ] Maps to Supabase `products` schema (name, price, image_url, affiliate_url, category, brand)
- [ ] Deduplicates by product ID before inserting
- [ ] Filters to emerging/mid-tier brands (SNITCH, Bewakoof, Cord, Urbanic, Indya)
- [ ] Runs on a cron (daily refresh)
- [ ] Logs import count and errors

**Priority**: 🟠 P1 · **Effort**: M · **Value**: 9/10

---

### Story E10-3 · Brand context seeding
**As a** content manager  
**I want** curated brand context notes in the product catalog  
**So that** Mira can speak about brand reputation without fetching live reviews

**Acceptance criteria**
- [ ] `brand_notes` column added to `products` table
- [ ] 10 emerging brands seeded with notes (e.g. "SNITCH: rated for quality basics under ₹1,500, true to size, strong community reviews")
- [ ] Notes injected into Mira's grounding prompt alongside product data

**Priority**: 🟠 P1 · **Effort**: XS · **Value**: 8/10

---

### Story E10-4 · Commission disclosure
**As a** legal requirement  
**I want** affiliate disclosure language visible to users  
**So that** we comply with ASA / ASCI India advertising guidelines

**Acceptance criteria**
- [ ] "Mira earns a small commission on purchases — your price is never affected" visible near product cards
- [ ] Disclosure in privacy policy (already done in E6)
- [ ] Affiliate links use `rel="noopener noreferrer nofollow sponsored"`

**Priority**: 🟠 P1 · **Effort**: XS · **Value**: 7/10

---

## E11 · Amazon PA-API + Reviews

### Story E11-1 · PA-API integration
**As a** developer  
**I want** Amazon Product Advertising API wired up  
**So that** Amazon India products have real pricing, images, and availability

**Acceptance criteria**
- [ ] `AMAZON_ACCESS_KEY`, `AMAZON_SECRET_KEY`, `AMAZON_PARTNER_TAG` in .env
- [ ] `product_source.py` Amazon source queries PA-API for search + ASIN lookup
- [ ] Products saved to Supabase with `source: "amazon"`
- [ ] Affiliate URLs use correct partner tag

**Priority**: 🟠 P1 · **Effort**: M · **Value**: 9/10

---

### Story E11-2 · Reviews in product data
**As a** shopper  
**I want** Mira to mention real customer feedback when recommending products  
**So that** I can make more confident purchase decisions

**Acceptance criteria**
- [ ] PA-API review data (rating, review count, top review snippet) stored in `products` table
- [ ] Injected into Mira's per-product context in the grounding prompt
- [ ] Mira says "4.3 stars from 1,200 reviews — customers love the fit" naturally
- [ ] Only for Amazon-sourced products (honest fallback: no mention if no data)

**Priority**: 🟠 P1 · **Effort**: S · **Value**: 9/10

---

### Story E11-3 · Mira's own rating layer
**As a** shopper  
**I want** to rate products I've bought through Mira  
**So that** future recommendations improve and other users benefit

**Acceptance criteria**
- [ ] "Rate this" prompt appears 7 days after a `buy_click` event
- [ ] 1–5 star rating stored in `user_history` with `action: "rated"`
- [ ] Aggregate rating shown on `ProductCard` when ≥3 ratings exist
- [ ] Mira can reference these ratings in conversation

**Priority**: 🟡 P2 · **Effort**: M · **Value**: 8/10

---

## E12 · Network Quality (Safari/iOS fix)

### Story E12-1 · Latency-based network probe
**As a** mobile user on Safari/iOS  
**I want** network quality detection to actually work on my device  
**So that** the auto-switch to silent mode fires correctly (not just on Chrome/Android)

**Acceptance criteria**
- [ ] `navigator.connection` replaced with WebSocket ping probe
- [ ] On session start, send `{type:"ping"}` and measure round-trip time
- [ ] RTT > 800ms → treat as "slow", show warning before voice
- [ ] RTT > 2000ms → auto-switch to silent
- [ ] Works on Safari 16+, Chrome, Firefox

**Priority**: 🟠 P1 · **Effort**: XS · **Value**: 8/10

---

## Immediate next actions (this sprint)

1. **Run `migrate_user_preferences.sql`** in Supabase SQL Editor — 10 seconds, unblocks preferences saving _(user action)_
2. **E8-1** — Cart panel (fitting room UI) — half a day
3. **E8-2** — Try On fullscreen viewer — 2 hours
4. **E10-1** — VCommission signup _(user action — need publisher ID before E10-2 can start)_
5. **E9-2** — `video_url` column in Supabase + E9-1 video generation script _(once Runway/Kling API key obtained)_
6. **E12-1** — Network latency probe (Safari fix) — 2 hours
