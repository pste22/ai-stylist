"""Repeatable tests for the stylist brain — no network/API calls (all stubbed).

Run from the prototype/ dir:   pytest -q
Covers: price-intent parsing, category synonym grounding, and the P2-6 network
fallback paths (total failure, transient retry, mid-stream drop).
"""
from __future__ import annotations

import os

import pytest

# Stylist validates GROQ_API_KEY at construction; a dummy key is fine because we never
# actually call the network (the Groq client is stubbed in every test below).
os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")

import stylist as S  # noqa: E402
from stylist import Stylist, _parse_price_intent  # noqa: E402


# --- price-intent parsing -------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("a dress under $80", (80.0, False)),
    ("something below 100", (100.0, False)),
    ("less than 75 please", (75.0, False)),
    ("just the cheapest one", (None, True)),
    ("something around 50 budget", (50.0, True)),
    ("show me jackets", (None, False)),
    ("up to $40", (40.0, False)),
])
def test_parse_price_intent(text, expected):
    assert _parse_price_intent(text.lower()) == expected


# --- fake streaming chunks (shape the code reads: .choices[0].delta.content) ----

class _Delta:
    def __init__(self, c): self.content = c

class _Choice:
    def __init__(self, c): self.delta = _Delta(c)

class _Chunk:
    def __init__(self, content="", usage=None):
        self.choices = [_Choice(content)] if content is not None else []
        self.x_groq = usage

def _stream(words):
    for w in words:
        yield _Chunk(w)


@pytest.fixture
def stylist():
    return Stylist()


# --- category synonym grounding (offline; uses LocalJsonSource) ----------

def test_grounding_maps_sneakers_to_shoes(stylist):
    grounding = stylist._grounding("do you have white sneakers?")
    assert "shoes" in grounding.lower()

def test_grounding_price_cap_excludes_pricey(stylist):
    grounding = stylist._grounding("a dress under $60")
    # every rendered price should be <= 60
    prices = [float(p.split("$")[1].split(" ")[0]) for p in grounding.splitlines() if "$" in p]
    assert prices and all(p <= 60 for p in prices)


# --- P2-6 network fallback paths -----------------------------------------

def test_total_failure_falls_back(stylist):
    attempts = {"n": 0}
    def boom(*a, **k):
        attempts["n"] += 1
        raise ConnectionError("network down")
    stylist._client.chat.completions.create = boom

    out = "".join(stylist.reply_stream("I need a jacket"))
    assert out == S._FULL_FALLBACK
    assert attempts["n"] == S._MAX_RETRIES + 1          # tried once, retried once
    assert stylist._history[-2]["role"] == "user"        # history stays paired
    assert stylist._history[-1]["role"] == "assistant"


def test_transient_failure_retries_then_succeeds(stylist):
    state = {"first": True}
    def flaky(*a, **k):
        if state["first"]:
            state["first"] = False
            raise ConnectionError("one-time blip")
        return _stream(["Here ", "you ", "go."])
    stylist._client.chat.completions.create = flaky

    out = "".join(stylist.reply_stream("I need a jacket"))
    assert out == "Here you go."
    assert stylist._history[-1]["content"] == "Here you go."


def test_midstream_drop_closes_gracefully(stylist):
    def mid_fail(*a, **k):
        def gen():
            yield _Chunk("I ")
            yield _Chunk("love ")
            yield _Chunk("that")
            raise ConnectionError("dropped mid-stream")
        return gen()
    stylist._client.chat.completions.create = mid_fail

    out = "".join(stylist.reply_stream("jacket?"))
    assert out.startswith("I love that")
    assert out.endswith(S._MIDSTREAM_FALLBACK)
    assert stylist._history[-1]["content"] == out       # partial + tail persisted
