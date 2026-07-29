# Phase 4b — Groq Final Report & Email

Groq writes the stakeholder **final report** and **final email** from a validated fact pack **before** Google Docs / Gmail MCP delivery.

## Config

See `config/pulse.yaml` → `groq`:

- `enabled: true`
- `model: llama-3.3-70b-versatile`
- `api_key_env: GROQ_API_KEY`
- `max_tokens: 700` (a *ceiling*; the actual completion budget per call is clamped tighter — see below)
- `require_before_delivery: true`
- `limits`: `rpm`, `tpm`, `rpd`, `tpd` — the account's published free-tier limits

Set the key (never commit it):

```bash
# Windows PowerShell
$env:GROQ_API_KEY = "gsk_..."
```

Or copy `.env.example` → `.env` and load it in your shell.

## Rate limits (RPM / TPM / RPD / TPD)

Current defaults in `config/pulse.yaml` (`groq.limits`) match the `llama-3.3-70b-versatile` free tier:

| Limit | Value |
|-------|-------|
| Requests / minute | 30 |
| Tokens / minute | 1,000 |
| Requests / day | 12,000 |
| Tokens / day | 100,000 |

1,000 TPM is tight — a single request's prompt + completion can easily exceed it if not careful. `src/compose/rate_limit.py` handles this on a best-effort, client-side basis:

- **Compact prompt** — `src/compose/prompts.compact_fact_pack_for_prompt()` strips `review_ids` and other fields Groq doesn't need before building the prompt, and the JSON is serialized without indentation. This is what makes a request fit at all on a 1k TPM budget.
- **Pre-call token estimate + clamp (TPM)** — `estimate_tokens()` (≈4 chars/token heuristic) sizes the prompt, then `clamp_max_tokens()` caps the requested completion so `prompt + completion` stays under `tpm` (with a safety margin). If the prompt alone leaves no useful room, **no API call is made** (G-09) — retrying an oversized prompt cannot succeed.
- **429 backoff (RPM/TPM)** — a `groq.RateLimitError` mid-run triggers up to 3 retries, honoring the `Retry-After` header when present, else exponential backoff capped at ~65s (G-10).
- **Daily budget guard (RPD/TPD)** — `GroqUsageTracker` logs every call's actual token usage (from `response.usage`) to `output/groq-usage.json`. Before each call, `check_daily_budget()` refuses to call Groq at all if today's logged usage already meets/exceeds `rpd`/`tpd` (G-11). This is best-effort — it only knows what *this* pipeline has logged, not Groq's true server-side counters.

None of this guarantees success on an extremely constrained plan; it guarantees the pipeline **fails closed with a clear reason** instead of silently invoking Groq with a doomed request or spinning through retries that can't help.

## Inputs / outputs

| Artifact | Role |
|----------|------|
| `output/pulse-facts.json` | Fact pack from Phase 3 |
| `output/pulse-facts.validation.json` | Phase 4 pre-LLM validation result (written even on block) |
| `output/pulse-latest.md` | Groq final report → Docs body |
| `output/email-latest.json` | Groq final email `{subject, body}` with `{doc_link}` |
| `output/groq-meta.json` | Model / word count / retries |
| `output/groq-usage.json` | Best-effort local RPD/TPD usage log (last ~500 calls) |

## Run

```bash
pip install -r requirements.txt
python -m src.compose.cli --facts output/pulse-facts.json
```

`write_final_copy()` runs the Phase 4 pre-LLM validator (`src/validate/fact_pack.py`) first. If it fails, Groq is **never called** — no API request, no partial artifacts — and `output/pulse-facts.validation.json` records why. Only a passing fact pack proceeds to the Groq call below.

## Delivery gate

`src/compose/delivery_gate.py` blocks Docs/Gmail adapters until Groq artifacts exist and parse. Adapters call `require_delivery_ready()` before MCP.

## Modules

| Module | Role |
|--------|------|
| `src/validate/fact_pack.py` | Phase 4 pre-LLM gate (runs first, inside `write_final_copy`) |
| `src/compose/prompts.py` | System/user prompts + fact-pack compaction (verbatim quotes, no PII, ≤250 words) |
| `src/compose/rate_limit.py` | RPM/TPM/RPD/TPD awareness: token estimate, clamp, backoff, daily usage log |
| `src/compose/groq_writer.py` | Pre-LLM gate → rate-limit guards → Groq API → post-LLM validation + one retry |
| `src/compose/delivery_gate.py` | Pre-MCP gate |
| `src/compose/render.py` | `{iso_week}` / `{week_of}` pattern rendering for Docs title / Gmail subject |
| `src/validate/checks.py` | PII / word count / verbatim checks (post-LLM) |
