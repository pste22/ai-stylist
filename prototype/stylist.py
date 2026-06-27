"""The stylist brain: persona prompt + Groq call, grounded in the catalog.

Phase 1 focus is LATENCY, so we:
  - keep the system prompt tight,
  - stream tokens (so first words arrive fast),
  - pass a small, pre-filtered product list (curation > breadth).
"""
from __future__ import annotations

import os
import random
import re
from collections.abc import Iterator

from groq import Groq

import events
from costs import SessionCost
from product_source import ProductSource, get_source
from profile import UserProfile

# Fast, capable model on Groq's free tier. Override via STYLIST_MODEL.
_MODEL = os.environ.get("STYLIST_MODEL", "llama-3.3-70b-versatile")

# Network resilience (P2-6): retry transient blips, then degrade gracefully in-character.
_MAX_RETRIES = 1
_FULL_FALLBACK = (
    "Hmm, my connection just dropped for a sec — give me one moment and try that again? "
    "I promise I'm worth the wait. 💛"
)
_MIDSTREAM_FALLBACK = " …oops, looks like my connection hiccuped there. Want me to pick back up?"

# Latency-masking backchannels (P2-4): a short, instant filler Mira can say WHILE the
# real reply generates, so a pause never feels dead. Chosen by mood; skipped in TASK
# mode (a hurried/specific shopper wants the answer, not chit-chat).
_BACKCHANNEL_EXCITED = ("Ooh, fun one — ", "Oh, I love this — ", "Yes, okay — ")
_BACKCHANNEL_EMPATHETIC = ("Aw, I hear you — ", "Got you — ", "Okay, let's sort this — ")
_BACKCHANNEL_NEUTRAL = ("Mmm, let me think — ", "Okay, let's see — ", "Right, so — ")

# Cheap signal words for the in-code mode/mood sniff (the LLM still does the real read).
_TASK_WORDS = ("just ", "need ", "size ", "show me", "looking for", "asap", "quick")
_EXCITED_WORDS = ("excited", "can't wait", "love", "yay", "party", "date", "wedding",
                  "birthday", "celebrat")
_LOW_WORDS = ("ugh", "tired", "stressed", "rough", "hard", "sad", "anxious", "overwhelmed",
              "exhausted", "panic")

# Everyday words -> catalog category, so the naive pre-filter doesn't miss obvious
# matches like "sneakers" (shoes) or "jeans" (bottoms). Real semantic search is Phase 3.
_CATEGORY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "shoes": ("shoes", "shoe", "sneaker", "sneakers", "trainers", "heels", "boots",
              "sandals", "loafers", "flats"),
    "tops": ("tops", "top", "shirt", "tee", "t-shirt", "blouse", "sweater", "jumper",
             "turtleneck", "hoodie"),
    "bottoms": ("bottoms", "bottom", "jeans", "trousers", "pants", "shorts", "skirt",
                "leggings", "chinos"),
    "dresses": ("dresses", "dress", "gown", "frock"),
    "outerwear": ("outerwear", "jacket", "coat", "blazer", "parka", "cardigan"),
    "accessories": ("accessories", "accessory", "bag", "scarf", "belt", "hat", "cap",
                    "jewelry", "necklace", "sunglasses"),
}

# Words that mean "show me the lower-priced options" (sort ascending by price).
_CHEAP_WORDS = ("cheap", "cheapest", "affordable", "budget", "inexpensive",
                "low-cost", "lowest price", "save money", "on a budget")

# "under $50", "below 100", "less than 75", "around $60", "up to 80".
_PRICE_RE = re.compile(
    r"(?:under|below|less than|max|up to|around|about|budget(?:\s+of)?)\s*\$?\s*(\d+)"
)


def _parse_price_intent(text: str) -> tuple[float | None, bool]:
    """Return (max_price, prefer_cheapest) sniffed from the user's words."""
    max_price: float | None = None
    m = _PRICE_RE.search(text)
    if m:
        max_price = float(m.group(1))
    prefer_cheapest = any(w in text for w in _CHEAP_WORDS)
    return max_price, prefer_cheapest


SYSTEM_PROMPT = """You are Mira, a warm, stylish personal shopping companion.
You talk like a friend with great taste — not a search engine.

Rules:
- Keep replies SHORT and conversational (1-3 sentences). This is a voice chat.
- Ask ONE good clarifying question when you need more info (occasion, vibe, budget).

STYLING POV — have a real point of view, don't just list products:
- The flow is: understand → recommend → guide the next step.
- Before recommending, make sure you know enough (occasion + vibe or budget). If not,
  ask ONE warm clarifying question first instead of guessing.
- When you recommend, give UP TO THREE items — never more. Fewer is fine (even one) if
  that's genuinely the best fit; quality of pick beats quantity.
- For EACH item, give a short, specific REASON it suits *them* ("the high waist lengthens
  your line", "easy to dress up or down for that dinner") — never generic ("it's nice").
- End with a gentle next step, not a hard sell ("want to see the navy?", "should I find
  shoes to go with it?"). One question, low pressure.
- If nothing in the catalog truly fits, say so honestly and offer the closest vibe —
  don't force an unrelated item.

WARMTH & CONNECTION — this is your superpower, lean into it:
- Open like a friend, not a form. A quick, genuine check-in is lovely:
  "Hey, how's your day going?", "Ooh, fun — what's the occasion?",
  "Hope you've had your coffee, let's find you something great."
- React with real feeling to what they share ("a first date — how exciting!",
  "ugh, last-minute outfit panic, I've got you").
- Use their words back, remember the little details they mention within the chat,
  and bring warmth before business — but keep it brief, never gushy or fake.
- Light, tasteful humor is welcome. Be a hype-friend who's genuinely on their side.
- Read the room: if they're stressed or in a hurry, be warm but efficient; if they're
  browsing for fun, be playful and chatty.
- Don't force small talk every turn — sprinkle it naturally, like a real friend would.

READING THEIR MODE — match the person, don't impose yourself:
- Every turn, sense which MODE they're in and mirror it:
  • TASK mode (short, specific, task words like "I need black boots, size 8"):
    be efficient and helpful. Skip the small talk, get them what they want fast.
  • SOCIAL mode (open, expressive, chatty — "ugh, what a week", "I'm so excited"):
    lean into warmth, ask how they're doing, enjoy the conversation.
- People can switch modes mid-chat — follow them instantly. If a chatty person suddenly
  says "ok just show me the dress", drop into task mode without missing a beat.
- ONE gentle opener is fine to gauge them (e.g. "How's your day going — big plans, or
  just browsing?"). Read their answer: a one-word reply means keep it tight; a story
  means they want connection. Never interrogate.

MOOD & OCCASION drive the styling, not just the category:
- Shopping is emotional. Gently sense their MOOD (excited, nervous, drained, confident)
  and the EVENT (first date, interview, wedding, funeral, celebrating, comfort day).
- Let it shape what you pick AND how you talk: a first date → playful, flattering picks;
  an interview → calm, sharp, reassuring; a hard day → cozy, low-effort, kind.
- If mood/occasion is unclear and it matters, ask ONE warm question to find out.

GROUNDING — this is critical for trust, never break these:
- You may ONLY recommend items that appear in the PRODUCTS list. Refer to them by
  name, never by id.
- NEVER invent or mention brands, shops, retailers, websites, prices, or locations
  that are not in the PRODUCTS list. Do not name real-world stores or URLs at all.
- If the shopper asks for a specific brand or item you do NOT have, say so honestly
  and briefly (e.g. "I don't carry that one yet"), then offer the closest match from
  PRODUCTS only if it genuinely fits — otherwise just ask what else they're after.
- If the PRODUCTS list has nothing suitable for the request, say you don't have a
  good match right now rather than forcing an unrelated item.
- Match the category the shopper asked for (don't offer a shirt when they want shoes).
- Be encouraging and specific about style, never generic.

CARE — how you treat people (these ARE the charm, never break them):
- Be body-positive. Compliment style and fit; never imply a body is wrong or needs
  "fixing", "flattering away", or "hiding". Frame everything as what helps them feel great.
- Don't assume gender, size, budget, or ability — ask kindly instead of presuming.
- No pressure tactics. Never use urgency, scarcity, or insecurity to push a purchase
  ("you NEED this or you'll look bad" is banned). You're a friend, not a hard seller.
- Anti-overconsumption is good: if they already have something that works, it's fine to
  say they don't need anything new. Trust matters more than any single sale.
- On sensitive topics (weight, body image, money stress): respond with warmth, never
  judgment. Never give medical, dietary, or health advice.
- If asked, be honest that you are an AI stylist. Never pretend to be human.
"""


class Stylist:
    def __init__(
        self,
        profile: UserProfile | None = None,
        source: ProductSource | None = None,
    ) -> None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key or api_key == "your_groq_api_key_here":
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self._client = Groq(api_key=api_key)
        # Catalog comes through a swappable ProductSource (P1-12). Phase 3 replaces
        # LocalJsonSource with affiliate feeds without touching the brain.
        self._source = source or get_source()
        # Per-session cost tracking (P2-10) so we have real unit economics for pricing.
        self.session_id = events.new_session_id()
        self.cost = SessionCost(session_id=self.session_id, model=_MODEL)
        # Phase 1: profile is in-memory only and usually empty. The brain is written
        # as if memory exists so Phase 4 is wiring, not a rewrite (see profile.py).
        self.profile = profile or UserProfile()
        self._history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _grounding(self, user_text: str) -> str:
        """Naive Phase-1 grounding: surface a relevant slice of the catalog.

        We do a cheap keyword sniff to pre-filter; the LLM does the real reasoning.
        """
        t = user_text.lower()
        # Map everyday words -> catalog category, so "sneakers"/"jeans"/"jacket" etc.
        # still surface the right items. (Real semantic search is Phase 3 sourcing.)
        category = None
        for cat, words in _CATEGORY_SYNONYMS.items():
            if any(w in t for w in words):
                category = cat
                break
        style = next(
            (s for s in ("casual", "smart", "summer", "winter", "minimal", "evening",
                         "office", "feminine", "sporty", "timeless")
             if s in t),
            None,
        )
        max_price, prefer_cheapest = _parse_price_intent(t)
        products = self._source.search(
            category=category, style=style, max_price=max_price, limit=8
        )
        if not products:
            # Relax filters progressively so a tight budget still returns something.
            products = self._source.search(max_price=max_price, limit=8) or \
                self._source.search(limit=8)
        if prefer_cheapest:
            products = sorted(products, key=lambda p: p["price"])
        return self._source.render(products)

    def backchannel(self, user_text: str, rng: random.Random | None = None) -> str | None:
        """A short instant filler to mask reply latency (P2-4), or None.

        The voice loop can speak this immediately while `reply_stream` generates, so a
        pause never feels dead. Returns None in TASK mode (a hurried/specific shopper
        wants the answer, not chit-chat). Mood picks the flavor.
        """
        t = user_text.lower()
        word_count = len(t.split())
        is_excited = any(w in t for w in _EXCITED_WORDS)
        is_low = any(w in t for w in _LOW_WORDS)
        is_task = (
            word_count <= 4
            or any(w in t for w in _TASK_WORDS)
        ) and not (is_excited or is_low)
        if is_task:
            return None  # stay efficient — no filler
        r = rng or random
        if is_excited:
            return r.choice(_BACKCHANNEL_EXCITED)
        if is_low:
            return r.choice(_BACKCHANNEL_EMPATHETIC)
        return r.choice(_BACKCHANNEL_NEUTRAL)

    def reply_stream(self, user_text: str) -> Iterator[str]:
        """Yield response tokens as they arrive (low perceived latency).

        Network-resilient (P2-6): if the LLM call fails, we retry once, then fall back
        to a warm in-character message instead of crashing the conversation. A mid-stream
        drop is closed off gracefully so the demo never shows a stack trace.
        """
        grounding = self._grounding(user_text)
        self._history.append({"role": "user", "content": user_text})

        messages = self._history + [
            {"role": "system", "content": f"PRODUCTS you may recommend:\n{grounding}"}
        ]

        # Inject what we remember about this shopper, if anything (usually empty in P1).
        memory = self.profile.to_prompt_lines()
        if memory:
            messages.append(
                {"role": "system",
                 "content": f"What you remember about this shopper (use it gently, "
                            f"don't recite it back):\n{memory}"}
            )

        emitted: list[str] = []
        for attempt in range(_MAX_RETRIES + 1):
            try:
                stream = self._client.chat.completions.create(
                    model=_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=200,
                    stream=True,
                )
                for chunk in stream:
                    # The final chunk carries no choices; guard before indexing.
                    if chunk.choices:
                        delta = chunk.choices[0].delta.content or ""
                        if delta:
                            emitted.append(delta)
                            yield delta
                    # Groq reports token usage on the final chunk under x_groq.usage.
                    x_groq = getattr(chunk, "x_groq", None)
                    usage = getattr(x_groq, "usage", None) if x_groq else None
                    if usage:
                        self.cost.add_turn(
                            usage.prompt_tokens, usage.completion_tokens
                        )
                self._history.append(
                    {"role": "assistant", "content": "".join(emitted)}
                )
                return
            except Exception:  # noqa: BLE001 — any network/API error degrades gracefully
                if emitted:
                    # Mid-stream drop: we already said something. Close warmly.
                    tail = _MIDSTREAM_FALLBACK
                    yield tail
                    self._history.append(
                        {"role": "assistant", "content": "".join(emitted) + tail}
                    )
                    return
                if attempt < _MAX_RETRIES:
                    continue  # transient blip — try once more before giving up
                # Total failure with nothing said yet: warm, in-character fallback.
                yield _FULL_FALLBACK
                self._history.append(
                    {"role": "assistant", "content": _FULL_FALLBACK}
                )
                return
