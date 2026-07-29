# Phase 4 — Compose & Validate (pre-LLM gate)

The fact pack itself is built in Phase 3 (`PulsePayload.to_fact_pack()` → `output/pulse-facts.json`). Phase 4's job is the **pre-LLM Constraint Validator** that must pass before Groq (Phase 4b) is ever called.

## What it checks

`src/validate/fact_pack.py::validate_fact_pack()`:

| Check | Type | Notes |
|-------|------|-------|
| `themes_all` ≤ `themes.max` | Hard | mirrors T-05 |
| `themes_top` ≤ `pulse.top_themes` | Hard | |
| `quotes` count vs `pulse.quotes` | Hard if over; warning if under **and** `allow_sparse` | empty-window safe |
| `actions` count vs `pulse.actions` | Hard if over; warning if under **and** `allow_sparse` | |
| PII in any quote/action text | Hard | reuses `src/validate/checks.find_pii` |
| Quote verbatim in `data/processed/anonymized.json` | Hard if corpus found; warning if corpus missing | Q-06 / G-03 defense-in-depth |
| Action grounded in a known `theme_id` | Hard | A-03 |
| `stats.total_reviews == sum(stats.by_store)` | Hard | V-03 |

Hard errors set `ok: false`; Groq is never called and no partial artifacts are written. Sparse-data shortfalls with `allow_sparse: true` are warnings only — the empty/limited-window path stays unblocked.

## Run standalone

```bash
python -m src.validate.cli --facts output/pulse-facts.json
```

Writes `output/pulse-facts.validation.json` and exits non-zero on hard failure.

## Enforcement point

`src/compose/groq_writer.write_final_copy()` calls `validate_fact_pack()` first, before any Groq API call. On failure it raises `GroqWriteError` and writes the same diagnostic file — so running Phase 4b directly (`python -m src.compose.cli`) without a clean Phase 4 pass is blocked automatically, not just when the standalone CLI is used.

## Modules

| Module | Role |
|--------|------|
| `src/validate/fact_pack.py` | Pre-LLM Constraint Validator |
| `src/validate/cli.py` | Standalone Phase 4 CLI |
| `src/compose/facts.py` | Load/persist fact pack JSON |
