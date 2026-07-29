# Phase 1 — Ingest & Normalize

Public-export ingest producing canonical reviews for the configured 8–12 week window.

## Run

```bash
pip install -r requirements.txt
python -m src.ingest.cli --as-of 2026-07-28
```

Options: `--config`, `--as-of YYYY-MM-DD`, `--no-persist`, `-v`.

## Output

`data/processed/canonical.json` — pre-redaction corpus + metrics (Phase 2 will anonymize).

## Modules

| Module | Role |
|--------|------|
| `src/config.py` | Load `pulse.yaml`; reject `window_weeks` outside 8–12 |
| `src/models.py` | `Review`, `IngestMetrics`, `IngestResult` |
| `src/ingest/loader.py` | CSV/JSON public exports only |
| `src/ingest/normalize.py` | Aliases → canonical; stable non-PII ids; drop identity fields |
| `src/ingest/window.py` | Inclusive date window |
| `src/ingest/pipeline.py` | End-to-end ingest + metrics + persist |
| `src/ingest/cli.py` | CLI entrypoint |

## Exit criteria

- [x] Both stores load (partial store degrades with warnings)
- [x] Window respects 8–12 weeks config
- [x] Malformed rows skipped with counts; empty window warned
- [x] No scrape/login automation

## Downstream note

After analysis (Phases 2–4), **Groq** writes the final report/email (Phase 4b) before Docs/Gmail MCP. See `docs/phase4b/GROQ_FINAL_COPY.md`.
