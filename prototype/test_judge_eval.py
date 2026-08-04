"""Offline unit tests for LLM-as-judge parsing / normalization (no API calls)."""
from __future__ import annotations

from functional.judge import (
    JudgeResult,
    _extract_json,
    _normalize_judge_payload,
    judge_turn,
)


def test_extract_json_direct():
    data = _extract_json('{"pass": true, "scores": {"relevance": 5}, "critical_failures": [], "summary": "ok"}')
    assert data["pass"] is True
    assert data["scores"]["relevance"] == 5


def test_extract_json_from_fence():
    raw = 'Here is my verdict:\n```json\n{"pass": false, "scores": {}, "critical_failures": ["hallucination"], "summary": "bad"}\n```'
    data = _extract_json(raw)
    assert data["pass"] is False
    assert "hallucination" in data["critical_failures"]


def test_normalize_fails_on_critical_list():
    jr = _normalize_judge_payload({
        "pass": True,
        "scores": {"relevance": 5, "grounding": 5, "budget": 5, "helpfulness": 4, "safety_boundary": 5},
        "critical_failures": ["invented Nike in stock"],
        "summary": "should fail",
    })
    assert jr.passed is False
    assert "invented Nike in stock" in jr.critical_failures


def test_normalize_fails_on_low_grounding_score():
    jr = _normalize_judge_payload({
        "pass": True,
        "scores": {"relevance": 4, "grounding": 2, "budget": 4, "helpfulness": 4, "safety_boundary": 5},
        "critical_failures": [],
        "summary": "weak grounding",
    })
    assert jr.passed is False
    assert any("grounding" in f for f in jr.critical_failures)


def test_normalize_pass_when_clean():
    jr = _normalize_judge_payload({
        "pass": True,
        "scores": {"relevance": 5, "grounding": 4, "budget": 5, "helpfulness": 4, "safety_boundary": 5},
        "critical_failures": [],
        "summary": "Good budget-aware reply",
    })
    assert jr.passed is True
    assert jr.avg_score and jr.avg_score >= 4


def test_judge_turn_empty_reply_no_api():
    jr = judge_turn(user_text="hi", mira_text="   ")
    assert jr.passed is False
    assert "empty_mira_reply" in jr.critical_failures


def test_judge_result_to_dict_has_pass_key():
    jr = JudgeResult(passed=True, scores={"relevance": 5}, summary="ok", provider="test")
    d = jr.to_dict()
    assert d["pass"] is True
    assert d["passed"] is True
