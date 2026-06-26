"""The stylist brain: persona prompt + Groq call, grounded in the catalog.

Phase 1 focus is LATENCY, so we:
  - keep the system prompt tight,
  - stream tokens (so first words arrive fast),
  - pass a small, pre-filtered product list (curation > breadth).
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from groq import Groq

from catalog import load_catalog, search, to_prompt_lines

# Fast, capable model on Groq's free tier. Override via STYLIST_MODEL.
_MODEL = os.environ.get("STYLIST_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """You are Mira, a warm, stylish personal shopping companion.
You talk like a friend with great taste — not a search engine.

Rules:
- Keep replies SHORT and conversational (1-3 sentences). This is a voice chat.
- Ask ONE good clarifying question when you need more info (occasion, vibe, budget).
- When recommending, suggest at most THREE items and say WHY each suits them.
- Only recommend items from the PRODUCTS list. Refer to them by name, never by id.
- Be encouraging and specific about style, never generic.
"""


class Stylist:
    def __init__(self) -> None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key or api_key == "your_groq_api_key_here":
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self._client = Groq(api_key=api_key)
        self._catalog = load_catalog()
        self._history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _grounding(self, user_text: str) -> str:
        """Naive Phase-1 grounding: surface a relevant slice of the catalog.

        We do a cheap keyword sniff to pre-filter; the LLM does the real reasoning.
        """
        t = user_text.lower()
        category = next(
            (c for c in ("tops", "bottoms", "dresses", "outerwear", "shoes", "accessories")
             if c[:-1] in t or c in t),
            None,
        )
        style = next(
            (s for s in ("casual", "smart", "summer", "winter", "minimal", "evening",
                         "office", "feminine", "sporty", "timeless")
             if s in t),
            None,
        )
        products = search(self._catalog, category=category, style=style, limit=8)
        if not products:
            products = self._catalog[:8]
        return to_prompt_lines(products)

    def reply_stream(self, user_text: str) -> Iterator[str]:
        """Yield response tokens as they arrive (low perceived latency)."""
        grounding = self._grounding(user_text)
        self._history.append({"role": "user", "content": user_text})

        messages = self._history + [
            {"role": "system", "content": f"PRODUCTS you may recommend:\n{grounding}"}
        ]

        stream = self._client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=200,
            stream=True,
        )

        full = []
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full.append(delta)
                yield delta

        self._history.append({"role": "assistant", "content": "".join(full)})
