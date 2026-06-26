"""Phase 1 text loop — run this FIRST.

Validates the stylist brain and measures LLM latency in isolation, before we add
the complexity of audio. This is the cheapest way to test Risk #1 (latency) and
Risk #3 (taste/curation).

Usage:
    python text_loop.py

Type as a shopper would ("I need an outfit for a summer wedding on a budget").
Type 'quit' to exit. Latency to first token + total is printed each turn.
"""
from __future__ import annotations

import sys
import time

from dotenv import load_dotenv

load_dotenv()

from stylist import Stylist  # noqa: E402  (after load_dotenv so the key is present)


def main() -> None:
    try:
        stylist = Stylist()
    except RuntimeError as e:
        print(f"\n  ⚠️  {e}\n")
        sys.exit(1)

    print("\n  💬 Mira, your AI stylist (Phase 1 prototype). Type 'quit' to exit.\n")
    print("  Try: \"I need a smart outfit for the office, nothing over $100\"\n")

    while True:
        try:
            user = input("  you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  👋 bye!\n")
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit", "q"}:
            print("\n  👋 bye!\n")
            break

        start = time.perf_counter()
        first_token_at: float | None = None

        print("  mira ▸ ", end="", flush=True)
        for token in stylist.reply_stream(user):
            if first_token_at is None:
                first_token_at = time.perf_counter()
            print(token, end="", flush=True)
        total = time.perf_counter() - start

        ttft = (first_token_at - start) if first_token_at else total
        print(f"\n        ⏱  first token {ttft*1000:.0f}ms · total {total*1000:.0f}ms\n")


if __name__ == "__main__":
    main()
