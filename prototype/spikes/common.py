"""Shared bits for the S1 voice spike — keep both paths apples-to-apples.

THROWAWAY. Reuses the real catalog + persona so grounding is tested honestly, but
none of this should be imported by the main loop.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

# Make the prototype package importable when run from prototype/ or prototype/spikes/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog import load_catalog, to_prompt_lines  # noqa: E402
from stylist import SYSTEM_PROMPT  # noqa: E402  (reuse the SAME persona + grounding rules)


# The 6 scripted utterances. Same script for both paths = fair comparison.
# #3 and #4 are grounding traps; #5 is the barge-in test.
SCRIPT = [
    "Hey, I need something for a summer wedding.",
    "What's my budget look like — keep it under a hundred.",
    "Do you have white sneakers?",          # GROUNDING: in catalog -> should work
    "Actually, get me some Nike Air Max.",   # GROUNDING: NOT in catalog -> must refuse
    "wait, no—",                             # BARGE-IN: say this while Mira is talking
    "Okay show me one more option.",
]


def full_grounding_prompt() -> str:
    """Persona + the ENTIRE ~20-item catalog as one context block.

    For the spike we pass the whole catalog (it's tiny) so we isolate the model's
    ability to STAY grounded, not the quality of our pre-filtering.
    """
    catalog = load_catalog()
    products = to_prompt_lines(catalog)
    return f"{SYSTEM_PROMPT}\n\nPRODUCTS you may recommend:\n{products}"


def print_script() -> None:
    print("\n  📋 Speak these 6 lines, in order (record the audio):\n")
    for i, line in enumerate(SCRIPT, 1):
        tag = ""
        if i == 3:
            tag = "   ← grounding (IN catalog: must work)"
        elif i == 4:
            tag = "   ← grounding (NOT in catalog: must refuse honestly)"
        elif i == 5:
            tag = "   ← BARGE-IN: interrupt Mira mid-reply"
        print(f"    {i}. \"{line}\"{tag}")
    print()


class Stopwatch:
    """Measures end-of-user-speech -> first-audio-out per turn."""

    def __init__(self) -> None:
        self.turns: list[float] = []
        self._start: float | None = None

    def start_turn(self) -> None:
        """Call the instant the user STOPS speaking (end of utterance)."""
        self._start = time.perf_counter()

    def first_audio(self) -> None:
        """Call the instant the FIRST audio sample plays back."""
        if self._start is None:
            return
        ms = (time.perf_counter() - self._start) * 1000
        self.turns.append(ms)
        print(f"        ⏱  first audio: {ms:.0f}ms")
        self._start = None

    @property
    def median_ms(self) -> float:
        if not self.turns:
            return float("nan")
        s = sorted(self.turns)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


@contextmanager
def scorecard(path_name: str):
    """Wrap a run; prints the result template to paste into the spike doc."""
    sw = Stopwatch()
    print(f"\n  ── Spike S1 · {path_name} ──")
    print_script()
    try:
        yield sw
    finally:
        print("\n  ── RESULT (paste into docs/spikes/S1-gemini-live-spike.md) ──")
        print(f"    Path: {path_name}")
        print(f"    Median first-audio latency (4G): {sw.median_ms:.0f}ms")
        print(f"    Per-turn ms: {[round(t) for t in sw.turns]}")
        print("    Grounding (utterance #3 worked / #4 refused?): [ pass / fail ]")
        print("    Barge-in (utterance #5 interrupted Mira?):     [ pass / fail ]")
        print("    Voice warmth (Founder's gut, 1-5):             [ _ ]")
        print("    Notes:")
