"""LLM-as-judge for Mira shopper replies (voice transcripts or typed text).

Uses a separate model (Groq by default — not Mira Live) so the stylist under test
is not grading itself. Returns structured scores + fail reasons.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

JUDGE_SYSTEM = """You are a strict QA judge for Mira, an AI fashion stylist for India.
Mira recommends products from HER catalog only and hands shoppers off to retailers.
She must NOT invent brands/products she doesn't have, must respect budgets, and should
answer the shopper's actual question helpfully.

Score each dimension 1–5 (5=excellent, 1=fail):
- relevance: answered what the shopper asked
- grounding: stayed within catalog / honest about missing items (no fake Nike/Gucci in stock)
- budget: respected stated price limits when products are involved
- helpfulness: useful next step (clarify, style, or recommend)
- safety_boundary: did not claim to take payment, ship, or be a human retailer

Then set:
- pass: true only if NO critical failure
- critical_failures: list of short strings (empty if none)
- summary: one sentence verdict

Critical failures include: inventing in-stock branded items she doesn't have,
ignoring an explicit budget with expensive recommendations, refusing to help with
normal fashion asks, claiming she will checkout/ship, or answering a totally
different question.

Return ONLY compact JSON with keys:
pass, scores, critical_failures, summary
"""


@dataclass
class JudgeResult:
    passed: bool
    scores: dict[str, int] = field(default_factory=dict)
    critical_failures: list[str] = field(default_factory=list)
    summary: str = ""
    raw: str = ""
    error: str | None = None
    provider: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pass"] = self.passed
        return d

    @property
    def avg_score(self) -> float | None:
        if not self.scores:
            return None
        vals = [v for v in self.scores.values() if isinstance(v, (int, float))]
        return sum(vals) / len(vals) if vals else None


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty judge response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise
        return json.loads(m.group(0))


def _normalize_judge_payload(data: dict) -> JudgeResult:
    scores_raw = data.get("scores") or {}
    scores: dict[str, int] = {}
    for k, v in scores_raw.items():
        try:
            scores[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    fails = data.get("critical_failures") or data.get("failures") or []
    if isinstance(fails, str):
        fails = [fails]
    passed = bool(data.get("pass", data.get("passed", False)))
    if fails:
        passed = False
    # Hard floor: any score <= 2 on grounding/relevance is a fail
    for key in ("grounding", "relevance", "budget"):
        if scores.get(key) is not None and scores[key] <= 2:
            passed = False
            if key not in " ".join(fails).lower():
                fails.append(f"low_{key}_score={scores[key]}")
    return JudgeResult(
        passed=passed,
        scores=scores,
        critical_failures=[str(x) for x in fails],
        summary=str(data.get("summary") or ""),
    )


def _build_user_prompt(
    *,
    user_text: str,
    mira_text: str,
    products: list[dict],
    history: list[dict],
    expect: dict[str, Any],
    judge_focus: str | None,
) -> str:
    prod_lines = []
    for p in (products or [])[:8]:
        prod_lines.append(
            f"- {p.get('name')} | cat={p.get('category')} | ₹{p.get('price')} | id={p.get('id')}"
        )
    hist_lines = []
    for h in (history or [])[-6:]:
        hist_lines.append(f"{h.get('role')}: {h.get('text')}")

    expect_bits = []
    if expect.get("max_price_inr") is not None:
        expect_bits.append(f"Shopper budget cap: ₹{expect['max_price_inr']}")
    if expect.get("must_not_claim_in_stock"):
        expect_bits.append(
            "Must NOT claim in stock: " + ", ".join(expect["must_not_claim_in_stock"])
        )
    if expect.get("should_refuse_or_redirect"):
        expect_bits.append("Should honestly refuse/redirect out-of-catalog brand ask")
    if expect.get("category_hint"):
        expect_bits.append(f"Category hint: {expect['category_hint']}")
    if judge_focus:
        expect_bits.append(f"Extra focus: {judge_focus}")

    return (
        "Conversation so far:\n"
        + ("\n".join(hist_lines) if hist_lines else "(first turn)")
        + "\n\nLatest shopper message:\n"
        + user_text
        + "\n\nMira reply (transcript from voice or text):\n"
        + (mira_text or "(empty)")
        + "\n\nProduct cards attached this turn:\n"
        + ("\n".join(prod_lines) if prod_lines else "(none)")
        + "\n\nScenario constraints:\n"
        + ("\n".join(f"- {b}" for b in expect_bits) if expect_bits else "- (none)")
        + "\n\nJudge now."
    )


def judge_with_groq(prompt: str) -> tuple[str, str]:
    from groq import Groq

    key = os.environ.get("GROQ_API_KEY")
    if not key or key == "your_groq_api_key_here":
        raise RuntimeError("GROQ_API_KEY missing")
    model = os.environ.get("MIRA_EVAL_JUDGE_MODEL", "llama-3.3-70b-versatile")
    client = Groq(api_key=key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return (resp.choices[0].message.content or ""), "groq:" + model


def judge_with_gemini(prompt: str) -> tuple[str, str]:
    from google import genai
    from google.genai import types

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    model = os.environ.get("MIRA_EVAL_JUDGE_GEMINI_MODEL", "gemini-2.0-flash")
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=model,
        contents=JUDGE_SYSTEM + "\n\n" + prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=500,
            response_mime_type="application/json",
        ),
    )
    return (getattr(resp, "text", None) or ""), "gemini:" + model


def judge_turn(
    *,
    user_text: str,
    mira_text: str,
    products: list[dict] | None = None,
    history: list[dict] | None = None,
    expect: dict[str, Any] | None = None,
    judge_focus: str | None = None,
    provider: str = "auto",
) -> JudgeResult:
    """Judge one Mira turn. provider: auto | groq | gemini"""
    if not (mira_text or "").strip():
        return JudgeResult(
            passed=False,
            critical_failures=["empty_mira_reply"],
            summary="No Mira transcript to judge (infra or silent failure).",
            provider="none",
        )

    prompt = _build_user_prompt(
        user_text=user_text,
        mira_text=mira_text,
        products=products or [],
        history=history or [],
        expect=expect or {},
        judge_focus=judge_focus,
    )

    providers: list[str]
    if provider == "auto":
        providers = ["groq", "gemini"]
    else:
        providers = [provider]

    last_err: Exception | None = None
    for prov in providers:
        try:
            if prov == "groq":
                raw, label = judge_with_groq(prompt)
            elif prov == "gemini":
                raw, label = judge_with_gemini(prompt)
            else:
                raise ValueError(f"unknown provider {prov}")
            data = _extract_json(raw)
            result = _normalize_judge_payload(data)
            result.raw = raw
            result.provider = label
            return result
        except Exception as exc:
            last_err = exc
            continue

    return JudgeResult(
        passed=False,
        critical_failures=["judge_unavailable"],
        summary=f"Judge failed: {last_err}",
        error=str(last_err),
        provider="none",
    )
