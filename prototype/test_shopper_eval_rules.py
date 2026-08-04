"""Offline unit tests for shopper-eval rule flags (no live server / API)."""
from __future__ import annotations

from functional.evaluate import evaluate_turn


def test_budget_violation_flagged():
    tr = evaluate_turn(
        turn_index=1,
        user_text="tops under 2000",
        mira_text="Here are a few tops I love for you.",
        products=[{"id": "a", "name": "Silk Blouse", "price": 4500, "category": "tops"}],
        expect={"min_reply_chars": 10, "max_price_inr": 2000, "prefer_products": True},
    )
    assert not tr.ok
    assert any(f.code == "BUDGET_VIOLATION" for f in tr.flags)


def test_nike_hallucination_flagged():
    tr = evaluate_turn(
        turn_index=1,
        user_text="Do you have Nike Air Max?",
        mira_text="Yes — here's a Nike Air Max you can buy right now.",
        products=[],
        expect={
            "min_reply_chars": 10,
            "must_not_claim_in_stock": ["nike air max"],
            "should_refuse_or_redirect": True,
        },
    )
    assert not tr.ok
    assert any(f.code == "HALLUCINATED_IN_STOCK" for f in tr.flags)


def test_honest_redirect_passes():
    tr = evaluate_turn(
        turn_index=1,
        user_text="Do you have Nike Air Max?",
        mira_text="I don't have Nike Air Max in our catalog — want similar black sneakers instead?",
        products=[{"id": "s1", "name": "Black Everyday Sneaker", "price": 1999, "category": "shoes"}],
        expect={
            "min_reply_chars": 10,
            "must_not_claim_in_stock": ["nike air max"],
            "should_refuse_or_redirect": True,
        },
    )
    assert tr.ok
    assert not any(f.severity == "error" for f in tr.flags)


def test_audio_required():
    tr = evaluate_turn(
        turn_index=1,
        user_text="hi",
        mira_text="Hey! What are we dressing for today?",
        products=[],
        expect={"min_reply_chars": 10},
        audio_bytes=0,
        require_audio=True,
    )
    assert not tr.ok
    assert any(f.code == "NO_AUDIO" for f in tr.flags)


def test_retailer_boundary():
    tr = evaluate_turn(
        turn_index=1,
        user_text="can I buy here?",
        mira_text="Sure, enter your card and I'll ship it tomorrow.",
        products=[],
        expect={"min_reply_chars": 10},
    )
    assert not tr.ok
    assert any(f.code == "RETAILER_BOUNDARY" for f in tr.flags)


def test_majority_color_mix_warns_when_off_brief():
    tr = evaluate_turn(
        turn_index=1,
        user_text="purple tops",
        mira_text="Here are a few tops that could work for you.",
        products=[
            {"id": "a", "name": "Green Tee", "price": 999, "category": "tops", "color": "green"},
            {"id": "b", "name": "Orange Blouse", "price": 1200, "category": "tops", "color": "orange"},
            {"id": "c", "name": "Yellow Top", "price": 1100, "category": "tops", "color": "yellow"},
        ],
        expect={"min_reply_chars": 10, "majority_color_hint": "purple", "min_color_share": 0.5},
    )
    assert any(f.code == "COLOR_MIX_OFF_BRIEF" for f in tr.flags)


def test_complement_cues_detected():
    tr = evaluate_turn(
        turn_index=2,
        user_text="complete the look",
        mira_text="Love those pants — let's pair a soft top and some glasses.",
        products=[{"id": "t", "name": "Silk Top", "price": 1500, "category": "tops"}],
        expect={"min_reply_chars": 10, "expect_complement_cues": True},
    )
    assert tr.ok
    assert not any(f.code == "MISSING_COMPLEMENT_CUE" for f in tr.flags)


def test_missing_complement_cues_warns():
    tr = evaluate_turn(
        turn_index=2,
        user_text="complete the look",
        mira_text="Sure, here are more pants in navy.",
        products=[{"id": "b", "name": "Navy Pants", "price": 2000, "category": "bottoms"}],
        expect={"min_reply_chars": 10, "expect_complement_cues": True},
    )
    assert any(f.code == "MISSING_COMPLEMENT_CUE" for f in tr.flags)
