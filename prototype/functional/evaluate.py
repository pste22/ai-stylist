"""Rule-based suitability checks for Mira shopper replies.

Flags inaccurate / off-policy answers so periodic runs can catch regressions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Flag:
    code: str
    severity: str  # error | warn
    message: str
    turn: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TurnResult:
    turn: int
    user: str
    mira: str
    products: list[dict] = field(default_factory=list)
    audio_bytes: int = 0
    flags: list[Flag] = field(default_factory=list)
    latency_ms: float | None = None
    ok: bool = True
    judge: dict | None = None

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "user": self.user,
            "mira": self.mira,
            "products": [
                {"id": p.get("id"), "name": p.get("name"), "price": p.get("price"),
                 "category": p.get("category")}
                for p in self.products
            ],
            "audio_bytes": self.audio_bytes,
            "latency_ms": self.latency_ms,
            "ok": self.ok,
            "flags": [f.to_dict() for f in self.flags],
            "judge": self.judge,
        }


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def evaluate_turn(
    *,
    turn_index: int,
    user_text: str,
    mira_text: str,
    products: list[dict],
    expect: dict[str, Any],
    audio_bytes: int = 0,
    require_audio: bool = False,
) -> TurnResult:
    flags: list[Flag] = []
    mira_n = _norm(mira_text)
    result = TurnResult(
        turn=turn_index,
        user=user_text,
        mira=mira_text,
        products=list(products or []),
        audio_bytes=audio_bytes,
    )

    if not mira_n or len(mira_text.strip()) < int(expect.get("min_reply_chars") or 1):
        flags.append(Flag(
            "EMPTY_OR_SHORT_REPLY", "error",
            f"Mira reply too short ({len(mira_text.strip())} chars).",
            turn_index,
        ))

    for pat in expect.get("forbid_patterns") or []:
        if _norm(pat) and _norm(pat) in mira_n:
            flags.append(Flag(
                "FORBIDDEN_PHRASE", "error",
                f"Reply contains forbidden phrase: {pat!r}",
                turn_index,
            ))

    # Soft: should sound like a stylist (question or recommendation cue)
    if expect.get("should_ask_or_style"):
        stylist_cues = ("?", "recommend", "suggest", "look", "wear", "dress", "outfit",
                        "budget", "occasion", "color", "colour", "vibe", "style")
        if not any(c in mira_n for c in stylist_cues):
            flags.append(Flag(
                "WEAK_STYLIST_SIGNAL", "warn",
                "Reply doesn't clearly ask a clarifying question or style the user.",
                turn_index,
            ))

    if expect.get("prefer_products") and not products:
        flags.append(Flag(
            "NO_PRODUCTS", "warn",
            "Expected product cards for this shopping turn, but none were attached.",
            turn_index,
        ))

    max_price = expect.get("max_price_inr")
    if max_price is not None and products:
        over = [p for p in products if (p.get("price") or 0) > float(max_price) * 1.05]
        if over:
            names = ", ".join((p.get("name") or p.get("id") or "?")[:40] for p in over[:3])
            flags.append(Flag(
                "BUDGET_VIOLATION", "error",
                f"Recommended product(s) over ₹{max_price}: {names}",
                turn_index,
            ))

    cat_hint = expect.get("category_hint")
    if cat_hint and products:
        cats = {(p.get("category") or "").lower() for p in products}
        if cat_hint.lower() not in cats and not any(cat_hint.lower() in (p.get("name") or "").lower() for p in products):
            flags.append(Flag(
                "CATEGORY_MISMATCH", "warn",
                f"Expected products related to {cat_hint!r}; got categories {sorted(cats)}.",
                turn_index,
            ))

    # Curation mix: majority of cards should match the asked color (curiosity may diverge).
    color_hint = expect.get("majority_color_hint")
    if color_hint and products:
        from curation_mix import majority_color_ok, detect_color_key
        key = detect_color_key(color_hint) or color_hint.lower()
        if not majority_color_ok(products, key, min_share=float(expect.get("min_color_share") or 0.5)):
            flags.append(Flag(
                "COLOR_MIX_OFF_BRIEF", "warn",
                f"Expected majority of products to match color {color_hint!r}.",
                turn_index,
            ))
        curiosity_n = sum(1 for p in products if p.get("mix_role") == "curiosity")
        if curiosity_n > 1:
            flags.append(Flag(
                "TOO_MANY_CURIOSITY", "warn",
                f"Expected at most one curiosity pick; got {curiosity_n}.",
                turn_index,
            ))

    # Shopping buddy: reply should steer toward complements / full look.
    if expect.get("expect_complement_cues"):
        cues = (
            "top", "tops", "shirt", "blouse", "hat", "cap", "glasses", "sunglass",
            "accessor", "bag", "shoe", "complete", "look", "pair", "with",
            "jacket", "blazer", "jewellery", "jewelry", "earring",
        )
        if not any(c in mira_n for c in cues):
            flags.append(Flag(
                "MISSING_COMPLEMENT_CUE", "warn",
                "Expected shopping-buddy complement / complete-the-look language.",
                turn_index,
            ))

    # Grounding: must not claim fake brand is in stock
    for claim in expect.get("must_not_claim_in_stock") or []:
        c = _norm(claim)
        if not c:
            continue
        # If Mira names the brand AND affirms availability without refusal language
        if c in mira_n:
            refusal = any(w in mira_n for w in (
                "don't have", "do not have", "can't find", "cannot find",
                "not in", "don't stock", "do not stock", "not available",
                "instead", "similar", "i don't carry", "we don't have",
                "not something i have", "outside", "can't get",
            ))
            if not refusal:
                flags.append(Flag(
                    "HALLUCINATED_IN_STOCK", "error",
                    f"May be claiming out-of-catalog item as available: {claim!r}",
                    turn_index,
                ))
            # Also flag if a product card looks like that brand
            for p in products:
                pname = _norm(p.get("name") or "")
                if c.split()[0] in pname and c in pname:
                    flags.append(Flag(
                        "OUT_OF_CATALOG_PRODUCT_CARD", "error",
                        f"Product card looks like forbidden brand item: {p.get('name')}",
                        turn_index,
                    ))

    if expect.get("should_refuse_or_redirect"):
        refusal = any(w in mira_n for w in (
            "don't have", "do not have", "can't find", "cannot find",
            "not in", "instead", "similar", "don't stock", "we don't",
            "i don't carry", "not something", "can't get nike", "no nike",
        ))
        if not refusal and products:
            # Products shown for a Nike ask are suspicious unless clearly alternatives
            flags.append(Flag(
                "MISSING_REFUSAL", "warn",
                "Expected an honest redirect/refusal for out-of-catalog brand request.",
                turn_index,
            ))
        elif not refusal and not products:
            flags.append(Flag(
                "MISSING_REFUSAL", "error",
                "No clear refusal/redirect when shopper asked for out-of-catalog brand.",
                turn_index,
            ))

    if require_audio and audio_bytes < 1000:
        flags.append(Flag(
            "NO_AUDIO", "error",
            f"Audio mode expected PCM audio; received {audio_bytes} bytes.",
            turn_index,
        ))

    # Soft hallucination: inventing checkout on Mira
    if any(p in mira_n for p in ("pay me", "checkout here", "enter your card", "i'll ship")):
        flags.append(Flag(
            "RETAILER_BOUNDARY", "error",
            "Mira implied she handles payment/shipping (should hand off to retailer).",
            turn_index,
        ))

    result.flags = flags
    result.ok = not any(f.severity == "error" for f in flags)
    return result


def summarize(scenario_id: str, turn_results: list[TurnResult]) -> dict:
    errors = [f for tr in turn_results for f in tr.flags if f.severity == "error"]
    warns = [f for tr in turn_results for f in tr.flags if f.severity == "warn"]
    judge_fails = [
        tr.judge for tr in turn_results
        if tr.judge and not tr.judge.get("pass", tr.judge.get("passed", True))
    ]
    return {
        "scenario_id": scenario_id,
        "passed": all(tr.ok for tr in turn_results) and not errors and not judge_fails,
        "turns": [tr.to_dict() for tr in turn_results],
        "error_count": len(errors),
        "warn_count": len(warns),
        "judge_fail_count": len(judge_fails),
        "flags": [f.to_dict() for f in errors + warns],
    }
