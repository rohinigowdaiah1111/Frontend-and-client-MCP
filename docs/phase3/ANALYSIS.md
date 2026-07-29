# Phase 3 — Theme Analysis

Clusters anonymized reviews into ≤5 themes, ranks the top 3, selects up to 3 verbatim quotes, and generates up to 3 concrete, theme-grounded actions. Output feeds Phase 4b (Groq final copy).

## Run

```bash
# After Phase 1 + 2 artifacts exist:
python -m src.analysis.cli

# Or run ingest + privacy + analysis in one shot:
python -m src.analysis.cli --from-privacy --as-of 2026-07-28
```

## Output

`output/pulse-facts.json` — matches the `PulsePayload` shape (architecture §5) and is the direct input to `src/compose/groq_writer.py` (Phase 4b).

| Key | Description |
|-----|-------------|
| `themes_all` | ≤5 themes (config `themes.max`), overflow merged into `other` |
| `themes_top` | Ranked top N (config `pulse.top_themes`, default 3) |
| `quotes` | ≤3 verbatim substrings of anonymized review text |
| `actions` | ≤3 concrete actions, each linked to ≥1 top theme |
| `limitation_note` | Set when data is sparse/empty — never fabricated to hide it |

## Modules

| Module | Role |
|--------|------|
| `src/analysis/keywords.py` | Keyword/synonym classification per theme label |
| `src/analysis/clusterer.py` | Assign `theme_id`; group + cap at `theme_max` (merge overflow into `other`) |
| `src/analysis/ranker.py` | Score = 0.5·volume + 0.35·severity(low ratings) + 0.15·recency; deterministic tie-break |
| `src/analysis/quotes.py` | Verbatim, PII-free, one-per-top-theme quote selection |
| `src/analysis/actions.py` | Template-based grounded actions (fix vs. monitor angle by avg rating) |
| `src/analysis/pipeline.py` | Orchestrates the above into `PulsePayload` + fact pack file |

## Verified on sample data (2026-07-28, 10-week window)

- 26 anonymized reviews → 5 themes (onboarding, kyc, payments, statements, withdrawals)
- Top 3: `kyc` (0.9167), `withdrawals` (0.8543), `payments` (0.8467)
- 3 quotes, each an exact substring of `data/processed/anonymized.json`
- 3 actions, each grounded in exactly one top theme

## Exit criteria

- [x] `themes_all.length <= 5`
- [x] `themes_top.length <= 3`
- [x] Exactly 3 quotes when enough reviews; each a substring of a redacted review
- [x] Exactly 3 actions, each linked to >=1 top theme
- [x] No paraphrased/fake quotes

## Tests

```bash
python -m unittest tests.test_analysis -v
```
