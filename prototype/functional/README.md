# Mira shopper functional eval

Periodic end-to-end test: converse like a shopper over the live bridge, check suitability, and **flag inaccurate answers**.

Voice is judged via **transcripts** (same as typed chat). Audio mode additionally asserts PCM frames arrive.

## Two layers of checking

| Layer | What | When |
|---|---|---|
| **Rules** (`evaluate.py`) | Deterministic: budget on cards, hallucinated brands, empty reply, no audio | Always |
| **AI judge** (`judge.py`) | Separate LLM scores relevance / grounding / budget / helpfulness / safety | `--judge` |

The judge uses **Groq** first (not Mira Live), then Gemini fallback — so the model under test is not grading itself.

## Modes

| Mode | What it proves |
|---|---|
| `silent` | Typing / text_input path (shopper types; Mira replies via Live transcripts) |
| `audio` | Same conversation + **PCM audio frames** must arrive (voice-out path) |
| `both` | Runs each eligible scenario in both modes (default) |

## Run

Prereqs: `live_server.py` up + working `GEMINI_API_KEY` (Live credits).  
For `--judge`: `GROQ_API_KEY` (preferred) or Gemini text model credits.  
If Mira never replies, the report flags `NO_MIRA_REPLY` (infra — often depleted Gemini credits), not a styling regression.

```bash
# Terminal A — backend
cd prototype && source ../.venv/bin/activate
python live_server.py

# Terminal B — eval (rules only)
cd prototype && source ../.venv/bin/activate
python -m functional.run_shopper_eval --mode silent

# Rigorous: rules + LLM judge on every turn
python -m functional.run_shopper_eval --mode silent --judge
python -m functional.run_shopper_eval --judge --judge-provider groq
python -m functional.run_shopper_eval --scenario grounding_refuse_fake_brand --judge
```

Offline tests (no server / no Live):

```bash
cd prototype && pytest test_shopper_eval_rules.py test_judge_eval.py -q
```

## Reports

JSON reports land in `functional/reports/`:

- `shopper_eval_latest.json` — overwrite each run  
- `shopper_eval_<timestamp>.json` — history for comparing regressions  

Each turn may include a `judge` object (`pass`, `scores`, `critical_failures`, `summary`).  
Exit code `1` if any **error** flag or judge fail fires (warnings alone still pass).

## Flag codes (examples)

| Code | Meaning |
|---|---|
| `NO_MIRA_REPLY` | No transcript at all (Gemini/session infra) |
| `EMPTY_OR_SHORT_REPLY` | Mira said almost nothing |
| `BUDGET_VIOLATION` | Product cards over stated budget |
| `HALLUCINATED_IN_STOCK` | Claimed Nike/etc. as available |
| `MISSING_REFUSAL` | Didn't redirect on out-of-catalog brand |
| `AI_JUDGE_FAIL` | LLM judge marked the reply incorrect / critical failure |
| `NO_PRODUCTS` | Shopping turn with no cards (warn) |
| `NO_AUDIO` | Audio mode got no PCM |
| `RETAILER_BOUNDARY` | Implied Mira takes payment/shipping |
| `FORBIDDEN_PHRASE` | Blocked boilerplate / bad phrases |

## Add scenarios

Edit `scenarios.json`. Each turn has `user` + `expect` rules. Optional `judge_focus` (turn or scenario) steers the AI judge. Keep scenarios stable so periodic runs are comparable after enhancements.
