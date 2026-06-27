"""Read-only signals summary (P2-7 / P2-8 review).

Turns data/events.jsonl into the few numbers that actually matter for the demo
review: how many sessions, would-buy intent per session, the most-loved items, and
average cost per session. No writes, no PII — just a quick read of what users did.

Run:  .venv/bin/python prototype/signals.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

_EVENTS = Path(__file__).parent / "data" / "events.jsonl"


def _load() -> list[dict]:
    if not _EVENTS.exists():
        return []
    return [json.loads(line) for line in _EVENTS.read_text().splitlines() if line.strip()]


def summarize(rows: list[dict]) -> str:
    if not rows:
        return "No events yet. Run a session (talk to Mira, tap 'Love it') to capture signals."

    sessions = {r.get("session_id") for r in rows if r.get("session_id")}
    would_buy = [r for r in rows if r.get("event") == "would_buy"]
    costs = [r for r in rows if r.get("event") == "session_cost"]

    loved = collections.Counter(
        r.get("product_name") or r.get("product_id") for r in would_buy
    )
    buyers = {r.get("session_id") for r in would_buy}

    lines = ["Mira — signals summary", "=" * 28, ""]
    lines.append(f"Sessions:            {len(sessions)}")
    lines.append(f"Would-buy taps:      {len(would_buy)}")
    if sessions:
        lines.append(f"Sessions w/ intent:  {len(buyers)} ({len(buyers) / len(sessions):.0%})")
        lines.append(f"Taps per session:    {len(would_buy) / len(sessions):.2f}")

    if loved:
        lines += ["", "Most-loved items:"]
        for name, n in loved.most_common(5):
            lines.append(f"  {n:>3} ×  {name}")

    if costs:
        usd = [float(r.get("usd", 0)) for r in costs]
        lines += ["", f"Avg cost/session:    ${sum(usd) / len(usd):.4f}  (n={len(usd)})"]

    return "\n".join(lines)


if __name__ == "__main__":
    print(summarize(_load()))
