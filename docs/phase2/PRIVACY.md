# Phase 2 — Privacy Gate

Nothing identifiable leaves the safe corpus used by analysis, Groq, Docs, or Gmail.

## Run

```bash
# After Phase 1 (or combined):
python -m src.ingest.cli --as-of 2026-07-28
python -m src.privacy.cli

# Or ingest + redact in one step:
python -m src.privacy.cli --from-ingest --as-of 2026-07-28
```

## Outputs

| File | Role |
|------|------|
| `data/processed/canonical.json` | Phase 1 pre-redaction (debug only) |
| `data/processed/anonymized.json` | **Safe corpus** for Phases 3+ |
| `data/processed/anonymized.error.json` | Written only if gate blocks (fail closed) |

Downstream analysis/compose **must** read `anonymized.json`, not raw exports or (preferentially) not pre-redaction canonical.

## What gets scrubbed

| Pattern | Placeholder |
|---------|-------------|
| Email | `[email]` |
| Phone | `[phone]` |
| `@handle` | `[handle]` |
| UUID / IMEI / long hex | `[device_id]` |
| `I'm Name` / `My name is Name` | `[name]` |

Identity columns (`username`, `author`, `email`, `device_id`, …) are never kept on the review model (P-05).

## Fail closed (P-06)

If redaction throws or residual hard PII remains, the pipeline:

1. Sets `blocked=True`
2. Does **not** write a successful `anonymized.json` with unredacted text
3. Writes `anonymized.error.json` diagnostic instead

## Tests

```bash
python -m unittest tests.test_redactor -v
```

## Modules

| Module | Role |
|--------|------|
| `src/privacy/patterns.py` | Shared regexes / placeholders |
| `src/privacy/redactor.py` | `redact_text` / `redact_reviews` |
| `src/privacy/pipeline.py` | Load → redact → persist |
| `src/privacy/cli.py` | CLI entrypoint |
