"""Cost-per-session instrumentation (P2-10).

Voice + per-query LLM calls make cost variable and usage-driven, so we must MEASURE it
before we can price it (see docs/12-pricing-strategy.md). This module turns raw token
counts into dollars and accumulates them per session, so we can later answer the one
question pricing hinges on: *what does an active user actually cost us?*

Prices are editable estimates ($ per 1M tokens). Update as providers change.
Audio (Gemini Live) cost hooks are stubbed for when the voice path reports usage.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import events

# $ per 1,000,000 tokens. Rough public estimates — adjust to real invoices.
# Groq free tier is $0 today; we still track "shadow cost" at paid rates so the unit
# economics are honest for when we scale onto paid infrastructure.
_PRICING: dict[str, dict[str, float]] = {
    "llama-3.3-70b-versatile": {"in": 0.59, "out": 0.79},
    # Gemini Live (text tokens); audio billed separately via _AUDIO_* below.
    "gemini-3.1-flash-live-preview": {"in": 0.50, "out": 1.50},
}
_DEFAULT_PRICING = {"in": 0.60, "out": 0.80}

# Gemini Live audio, $ per 1M audio tokens (estimate). Used only by the voice path.
_AUDIO_IN_PER_M = 3.00
_AUDIO_OUT_PER_M = 12.00


def token_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    """Dollar cost of one LLM call's text tokens."""
    p = _PRICING.get(model, _DEFAULT_PRICING)
    return (in_tokens * p["in"] + out_tokens * p["out"]) / 1_000_000


def audio_cost(in_audio_tokens: int = 0, out_audio_tokens: int = 0) -> float:
    """Dollar cost of voice audio tokens (Gemini Live path)."""
    return (in_audio_tokens * _AUDIO_IN_PER_M
            + out_audio_tokens * _AUDIO_OUT_PER_M) / 1_000_000


@dataclass
class SessionCost:
    """Accumulates token usage + dollars for one conversation."""

    session_id: str
    model: str
    in_tokens: int = 0
    out_tokens: int = 0
    audio_in_tokens: int = 0
    audio_out_tokens: int = 0
    turns: int = 0
    usd: float = field(default=0.0)

    def add_turn(self, in_tokens: int, out_tokens: int) -> float:
        """Record one text turn's usage; returns the incremental cost."""
        cost = token_cost(self.model, in_tokens, out_tokens)
        self.in_tokens += in_tokens
        self.out_tokens += out_tokens
        self.turns += 1
        self.usd += cost
        return cost

    def add_audio(self, in_audio_tokens: int = 0, out_audio_tokens: int = 0) -> float:
        """Record voice audio usage for a turn; returns the incremental cost."""
        cost = audio_cost(in_audio_tokens, out_audio_tokens)
        self.audio_in_tokens += in_audio_tokens
        self.audio_out_tokens += out_audio_tokens
        self.usd += cost
        return cost

    def flush(self) -> dict:
        """Log the session's total cost as one event (call at session end)."""
        return events.log_event(
            "session_cost",
            session_id=self.session_id,
            model=self.model,
            turns=self.turns,
            in_tokens=self.in_tokens,
            out_tokens=self.out_tokens,
            audio_in_tokens=self.audio_in_tokens,
            audio_out_tokens=self.audio_out_tokens,
            usd=round(self.usd, 6),
        )
