# Phase 0 Foundations

Scaffolding and decisions for the Weekly Review Pulse. Completes Phase 0 of `implementationPlan.md`.

---

## Repository layout

```text
/
├── config/pulse.yaml
├── data/raw/                 # public exports + schema docs
├── data/processed/           # anonymized cache (later phases)
├── src/
│   ├── ingest/
│   ├── privacy/
│   ├── analysis/
│   ├── compose/
│   ├── validate/
│   └── adapters/             # Docs/Gmail MCP ports (stubs)
├── output/                   # pulse-facts, Groq report/email, then MCP
├── docs/phase0/
├── docs/phase1/
├── docs/phase4b/             # Groq final copy
├── problemStatement.md
├── architecture.md
├── implementationPlan.md
└── edge-case.md
```
---

## Configuration

`config/pulse.yaml` sets:

| Key | Value |
|-----|--------|
| `window_weeks` | 10 (within 8–12) |
| Themes | ≤5: onboarding, kyc, payments, statements, withdrawals |
| Pulse | top 3 themes, 3 quotes, 3 actions, ≤250 words |
| Delivery | Docs title + Gmail subject patterns; draft to configurable alias |
| Privacy | strip `username`, `author`, `email`, `device_id` |
| **Groq** | `enabled`, model, `GROQ_API_KEY` env, **`require_before_delivery: true`** |
| Runtime | `both` (agent-driven + scripted runner) |

**Secrets:** No Google OAuth client secrets or **`GROQ_API_KEY`** in this repo. Google auth stays in the MCP host; Groq key stays in environment (see `.env.example`).

---

## Sample exports

| File | Rows | Window fit |
|------|------|------------|
| `data/raw/app_store_reviews.csv` | 15 | May–Jul 2026 |
| `data/raw/play_store_reviews.csv` | 15 | May–Jul 2026 |

Column contracts: `data/raw/EXPORT_SCHEMA.md`.

---

## Runtime mode

**Choice: `both`**

- **Agent-driven** — run stages from Cursor; Groq writes final copy; MCP tools for Docs/Gmail.
- **Scripted** — CLI runner for weekly jobs; still **Groq-before-delivery**, then MCP adapters (not bespoke Google APIs).

**Critical delivery rule:** Phases 5–6 must not run until Phase 4b Groq artifacts exist (`output/pulse-latest.md`, `output/email-latest.json`). See `docs/phase4b/GROQ_FINAL_COPY.md`.

---

## MCP inventory (smoke)

See `docs/phase0/MCP_INVENTORY.md`.

**Status (2026-07-28):** Google Docs and Gmail MCP servers are **not** configured in this environment. Available servers today: `user-alphavantage`, `user-github`. Phase 5–6 are blocked until Docs/Gmail MCP servers are added to Cursor MCP config and authenticated there—not via app code.

---

## Phase 0 exit criteria

- [x] Layout + `pulse.yaml` exist
- [x] Sample public exports present for both stores
- [x] Docs/Gmail MCP tools listed (gap documented; not reachable until configured)
- [x] No Google OAuth client code as primary path (adapters are MCP ports only)
