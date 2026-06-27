"""Privacy-first user profile — the seed of Mira's memory (board task P1-11).

Why this exists now (Phase 1) even though memory ships in Phase 4:
  Memory is the retention moat (see docs/07-cofounder-discussion.md). If the brain is
  written as if memory exists from day one, Phase 4 is a wiring job, not a rewrite.

Legal/Trust guardrails baked in (see docs/09-legal-trust-safety-discussion.md):
  - DATA MINIMIZATION: store only small, structured style facts — never raw audio,
    never raw transcripts.
  - DELETABLE: forget() wipes everything; the profile is user-owned, not our asset.
  - In Phase 1 this lives in memory only (no disk). Persistence is a later, deliberate
    decision made WITH a privacy policy in place.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class UserProfile:
    """A tiny, structured snapshot of what Mira may remember about a shopper.

    Frozen so updates are explicit (return a new copy) — no accidental mutation of
    user data. All fields optional; we start knowing nothing and learn gently.
    """

    # Coarse, non-identifying style facts only. NO names, emails, addresses, audio.
    vibe: tuple[str, ...] = field(default_factory=tuple)        # e.g. ("minimal", "casual")
    budget_band: str | None = None                              # e.g. "under-100", "100-300"
    sizes: dict[str, str] = field(default_factory=dict)         # e.g. {"top": "M", "shoe": "9"}
    liked_item_ids: tuple[str, ...] = field(default_factory=tuple)
    last_summary: str | None = None                             # one-line recap of last chat

    def is_empty(self) -> bool:
        return not (self.vibe or self.budget_band or self.sizes
                    or self.liked_item_ids or self.last_summary)

    # ----- gentle, explicit updates (each returns a new profile) -----

    def with_vibe(self, *words: str) -> "UserProfile":
        merged = tuple(dict.fromkeys((*self.vibe, *(w.lower() for w in words))))
        return replace(self, vibe=merged)

    def with_budget(self, band: str) -> "UserProfile":
        return replace(self, budget_band=band)

    def with_size(self, kind: str, value: str) -> "UserProfile":
        return replace(self, sizes={**self.sizes, kind.lower(): value})

    def with_liked(self, item_id: str) -> "UserProfile":
        if item_id in self.liked_item_ids:
            return self
        return replace(self, liked_item_ids=(*self.liked_item_ids, item_id))

    def with_summary(self, summary: str) -> "UserProfile":
        return replace(self, last_summary=summary.strip() or None)

    def forget(self) -> "UserProfile":
        """Right-to-be-forgotten: return a clean, empty profile."""
        return UserProfile()

    def to_prompt_lines(self) -> str:
        """Compact, token-cheap context for the LLM. Empty -> empty string."""
        if self.is_empty():
            return ""
        parts: list[str] = []
        if self.last_summary:
            parts.append(f"- Last time: {self.last_summary}")
        if self.vibe:
            parts.append(f"- Style vibe: {', '.join(self.vibe)}")
        if self.budget_band:
            parts.append(f"- Budget: {self.budget_band}")
        if self.sizes:
            parts.append("- Sizes: " + ", ".join(f"{k} {v}" for k, v in self.sizes.items()))
        if self.liked_item_ids:
            parts.append(f"- Previously liked (ids): {', '.join(self.liked_item_ids)}")
        return "\n".join(parts)
