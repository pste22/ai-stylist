#!/usr/bin/env python3
"""Periodic shopper functional eval for Mira (silent typing + audio-out paths).

Converses like a shopper over the live WebSocket bridge, then flags inaccurate /
off-policy answers.

Prereqs:
  1. Backend running:  .venv/bin/python live_server.py
  2. Valid GEMINI_API_KEY in prototype/.env

Usage (from prototype/):
  .venv/bin/python -m functional.run_shopper_eval --judge
  .venv/bin/python -m functional.run_shopper_eval --mode silent --judge
  .venv/bin/python -m functional.run_shopper_eval --judge --judge-provider groq

Exit code 0 = all scenarios passed (warnings allowed). 1 = any error / judge fail.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROTO = ROOT.parent
if str(PROTO) not in sys.path:
    sys.path.insert(0, str(PROTO))

from functional.evaluate import Flag, evaluate_turn, summarize  # noqa: E402
from functional.judge import judge_turn  # noqa: E402
from functional.mira_session import MiraSession  # noqa: E402


def load_scenarios(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


async def run_scenario(
    scenario: dict,
    *,
    mode: str,
    ws_url: str,
    turn_timeout: float,
    use_judge: bool,
    judge_provider: str,
) -> dict:
    text_mode = mode == "silent"
    require_audio = mode == "audio"
    turns_out = []
    history: list[dict] = []

    async with MiraSession(
        ws_url,
        text_mode=text_mode,
        user_name=f"Eval-{scenario['id'][:16]}",
        turn_timeout=turn_timeout,
    ) as session:
        for i, turn in enumerate(scenario.get("turns") or [], start=1):
            user = turn["user"]
            expect = turn.get("expect") or {}
            print(f"    [{mode}] turn {i}: {user[:70]}{'…' if len(user) > 70 else ''}")
            cap = await session.ask(user)
            preview = (cap.mira_text[:120] + "…") if len(cap.mira_text) > 120 else cap.mira_text
            print(f"           Mira ({cap.latency_ms or 0:.0f}ms, "
                  f"{len(cap.products)} products, {cap.audio_bytes}B audio): {preview!r}")
            tr = evaluate_turn(
                turn_index=i,
                user_text=user,
                mira_text=cap.mira_text,
                products=cap.products,
                expect=expect,
                audio_bytes=cap.audio_bytes,
                require_audio=require_audio,
            )
            tr.latency_ms = cap.latency_ms
            if not cap.mira_text.strip():
                tr.flags = [Flag(
                    "NO_MIRA_REPLY",
                    "error",
                    "No Mira transcript received — check live_server logs "
                    "(often GEMINI_API_KEY / depleted credits). Not a content regression.",
                    i,
                )] + [f for f in tr.flags if f.code != "EMPTY_OR_SHORT_REPLY"]
                tr.ok = False

            if use_judge and cap.mira_text.strip():
                jr = await asyncio.to_thread(
                    judge_turn,
                    user_text=user,
                    mira_text=cap.mira_text,
                    products=cap.products,
                    history=history,
                    expect=expect,
                    judge_focus=turn.get("judge_focus") or scenario.get("judge_focus"),
                    provider=judge_provider,
                )
                tr.judge = jr.to_dict()
                print(f"           ⚖ judge ({jr.provider}) "
                      f"{'PASS' if jr.passed else 'FAIL'} "
                      f"avg={jr.avg_score and round(jr.avg_score, 2)} — {jr.summary}")
                if jr.critical_failures:
                    print(f"             failures: {jr.critical_failures}")
                if not jr.passed:
                    tr.flags.append(Flag(
                        "AI_JUDGE_FAIL",
                        "error",
                        jr.summary or "; ".join(jr.critical_failures) or "Judge marked fail",
                        i,
                    ))
                    tr.ok = False

            for fl in tr.flags:
                mark = "✗" if fl.severity == "error" else "!"
                print(f"           {mark} [{fl.severity}] {fl.code}: {fl.message}")
            if not tr.flags:
                print("           ✓ no flags")

            history.append({"role": "shopper", "text": user})
            history.append({"role": "mira", "text": cap.mira_text})
            turns_out.append(tr)
            await asyncio.sleep(0.8)

    summary = summarize(f"{scenario['id']}::{mode}", turns_out)
    summary["mode"] = mode
    summary["title"] = scenario.get("title")
    summary["judge_enabled"] = use_judge
    return summary


async def amain(args: argparse.Namespace) -> int:
    scenarios_path = Path(args.scenarios)
    data = load_scenarios(scenarios_path)
    scenarios = data.get("scenarios") or []
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] == args.scenario]
        if not scenarios:
            print(f"Unknown scenario id: {args.scenario}", file=sys.stderr)
            return 2

    modes = ["silent", "audio"] if args.mode == "both" else [args.mode]
    results = []
    print(f"\n✦ Mira shopper functional eval  ({args.ws})")
    print(f"  scenarios={len(scenarios)}  modes={modes}  "
          f"judge={'on:' + args.judge_provider if args.judge else 'off'}\n")

    for sc in scenarios:
        allowed = set(sc.get("modes") or ["silent", "audio"])
        for mode in modes:
            if mode not in allowed:
                print(f"  · skip {sc['id']} [{mode}] (not in scenario.modes)")
                continue
            print(f"  ▶ {sc['id']} — {sc.get('title')} [{mode}]")
            try:
                summary = await run_scenario(
                    sc,
                    mode=mode,
                    ws_url=args.ws,
                    turn_timeout=args.timeout,
                    use_judge=args.judge,
                    judge_provider=args.judge_provider,
                )
            except Exception as exc:
                summary = {
                    "scenario_id": f"{sc['id']}::{mode}",
                    "mode": mode,
                    "title": sc.get("title"),
                    "passed": False,
                    "error_count": 1,
                    "warn_count": 0,
                    "flags": [{
                        "code": "SESSION_ERROR",
                        "severity": "error",
                        "message": str(exc),
                    }],
                    "turns": [],
                }
                print(f"           ✗ SESSION_ERROR: {exc}")
            results.append(summary)
            status = "PASS" if summary.get("passed") else "FAIL"
            print(f"  → {status}  errors={summary.get('error_count')}  "
                  f"warns={summary.get('warn_count')}\n")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ws": args.ws,
        "modes": modes,
        "passed": all(r.get("passed") for r in results) if results else False,
        "results": results,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"shopper_eval_{stamp}.json"
    latest = out_dir / "shopper_eval_latest.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("═" * 56)
    print(f"  Overall: {'PASS' if report['passed'] else 'FAIL'}")
    print(f"  Report:  {out_path}")
    print("═" * 56)
    return 0 if report["passed"] else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Mira shopper functional evaluation")
    ap.add_argument("--ws", default="ws://localhost:8765", help="live_server WebSocket URL")
    ap.add_argument("--mode", choices=["silent", "audio", "both"], default="both")
    ap.add_argument("--scenario", default=None, help="Run a single scenario id")
    ap.add_argument(
        "--scenarios",
        default=str(ROOT / "scenarios.json"),
        help="Path to scenarios JSON",
    )
    ap.add_argument("--timeout", type=float, default=45.0, help="Per-turn timeout seconds")
    ap.add_argument(
        "--out-dir",
        default=str(ROOT / "reports"),
        help="Directory for JSON reports",
    )
    ap.add_argument(
        "--judge",
        action="store_true",
        help="Run LLM-as-judge on each Mira reply (Groq/Gemini). Rigorous correctness check.",
    )
    ap.add_argument(
        "--judge-provider",
        choices=["auto", "groq", "gemini"],
        default="auto",
        help="Judge model provider (default: auto = Groq then Gemini)",
    )
    args = ap.parse_args()
    try:
        raise SystemExit(asyncio.run(amain(args)))
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
