# Phase 11 — From Sample CSVs to Real App Store / Play Store Data

**Status:** design doc / not yet implemented. Written to plan the exact, step-wise
change needed to move this project from the two synthetic sample CSVs
(`data/raw/app_store_reviews.csv`, `data/raw/play_store_reviews.csv`) to real,
live reviews for a real app (this doc uses "Groww" as the example app), without
breaking anything the pipeline already guarantees (Phase 1's `I-06`: **public
exports only, no scrape/login automation** — see `docs/phase1/INGEST.md`).

---

## 1. Current state (what already works)

```
data/raw/*.csv  →  src/ingest (Phase 1)  →  data/processed/canonical.json
                →  src/privacy (Phase 2)  →  data/processed/anonymized.json
                →  src/analysis (Phase 3) →  output/pulse-facts.json
                →  src/compose (Phase 4b) →  output/pulse-latest.md, email-latest.json
                →  Docs/Gmail MCP (Phase 5-6)
                →  webapp/ dashboard (Phase 10)
```

The ingest loader (`src/ingest/loader.py`) already reads **any** CSV or JSON file
that matches the column names (or aliases) in `data/raw/EXPORT_SCHEMA.md` — it
has no idea whether the file came from a sample fixture or a real export. That
means **the pipeline itself needs zero changes** to run on real data; only the
*source* of `data/raw/*.csv` needs to change.

| File | Required columns | Aliases already handled |
|---|---|---|
| `app_store_reviews.csv` | `review_id`, `text` or `title`, `date` | `review`, `body`, `content`, `review_text`, `comment` → `text`; `star`/`stars`/`score` → `rating`; `created_date`/`review_date`/`created_at` → `date` |
| `play_store_reviews.csv` | same | same |

Identity columns (`username`, `author`, `email`, `device_id`, `reviewer_name`, …)
are dropped automatically by `src/ingest/normalize.py` even if present in the
export — so accidentally including them in a real export is not a data leak,
but exporting a file that *only* contains those columns and no text will fail
loading.

---

## 2. Why not just scrape the stores?

`src/ingest/loader.py`'s own docstring says it: **"public CSV/JSON exports
only (no scrape/login)"**, and `docs/phase1/INGEST.md` lists "No scrape/login
automation" as a Phase 1 exit criterion. This was a deliberate constraint, not
an oversight:

- Both Apple's and Google's Terms of Service restrict automated scraping of
  store pages; unofficial scraper libraries (`google-play-scraper`,
  `app-store-scraper`, etc.) work by parsing undocumented HTML/JSON endpoints
  that can change or get blocked without notice.
- The **official** path for an app you own is always an authenticated API
  (App Store Connect API, Google Play Developer API) or a manual CSV export —
  both are stable, ToS-compliant, and already fit this project's existing
  "public export" ingestion model without changing `src/ingest` at all.

So every option below produces a CSV/JSON file that lands in `data/raw/` (or
gets POSTed to a new upload endpoint) in the *same shape* the pipeline already
understands — nothing downstream of `src/ingest/loader.py` needs to know how
that file was produced.

---

## 3. Three ways to get real data in — pick based on what you have access to

| Option | Needs | Effort | Automation | Best for |
|---|---|---|---|---|
| **A. Manual export** | Access to App Store Connect / Play Console UI for the app | Minutes, no code | None (manual, recurring) | Fastest way to demo on real data today |
| **B. CSV upload in the webapp** | Nothing extra — just this app | ~half a day | Manual trigger, no cron | Non-technical operators refreshing data without touching git/filesystem |
| **C. Official Developer APIs** | You (or your org) must own/administer the app in App Store Connect and Google Play Console | 1-2 days | Fully automatic (scheduled) | Production use for an app you actually operate |

You can implement A today with **no code changes**. B and C are additive — pick
one or both depending on how "hands-off" you want data refresh to be.

---

## 4. Option A — Manual export (no code changes)

**Google Play Console:**
1. Play Console → your app → **Ratings and reviews**.
2. Use the **Download** action, or the "Export" option under the reviews table, to get a CSV.
3. Rename its columns (or add an alias in `TEXT_ALIASES`/`RATING_ALIASES`/`DATE_ALIASES` in `src/ingest/normalize.py`) to match `EXPORT_SCHEMA.md` if they don't already line up. Play Console's own export already uses close-enough column names (`Review Text`, `Star Rating`, `Review Submit Date and Time`) — map them once, either by renaming headers in the CSV or by adding the exact strings to the alias tuples.
4. Save as `data/raw/play_store_reviews.csv`, replacing the sample file.

**App Store Connect:**
1. App Store Connect → your app → **Ratings and Reviews**.
2. Apple doesn't offer a one-click bulk CSV export in the UI the way Play Console does; the practical route is the **App Store Connect API**'s Customer Reviews resource (see Option C) even for a "manual" one-off pull — or copy/paste for a small sample if you just need a handful of rows to demo.
3. Save as `data/raw/app_store_reviews.csv`.

**Then:** run the pipeline exactly as documented already:
```bash
python -m src.ingest.cli --as-of 2026-07-30
python -m src.privacy.cli
python -m src.analysis.cli
# or just open the webapp and click "Refresh data" — webapp/data.py calls
# ingest() -> anonymize() -> analyze() for you in one call
```

**Exit criteria:** `webapp`'s dashboard shows real review counts/categories instead of the 25-30 sample rows.

---

## 5. Option B — Add a CSV upload endpoint to `webapp/`

Lets an operator replace `data/raw/*.csv` from the browser instead of editing
files/git directly. This is the smallest code change that removes "someone
with terminal access" as a bottleneck.

### Files to add/change

1. **`webapp/app.py`** — new endpoint:
   ```python
   from fastapi import UploadFile, File

   @app.post("/api/upload/{store}", dependencies=[Depends(require_session)])
   async def upload_reviews(store: str, file: UploadFile = File(...)) -> dict[str, Any]:
       if store not in ("app_store", "play_store"):
           raise HTTPException(400, "store must be app_store or play_store")
       cfg = load_config()
       source = next((s for s in cfg.sources if s.name == store), None)
       if source is None:
           raise HTTPException(500, f"No configured source path for {store}")

       raw = await file.read()
       # Validate before overwriting: reuse the same loader/normalizer the
       # pipeline itself uses, so a bad upload fails loudly here instead of
       # silently degrading a later ingest run.
       tmp = source.path.with_suffix(".upload_tmp" + source.path.suffix)
       tmp.write_bytes(raw)
       try:
           rows = load_rows(tmp)  # src.ingest.loader.load_rows
           normalized = 0
           for row in rows:
               try:
                   normalize_row(row, store)  # src.ingest.normalize.normalize_row
                   normalized += 1
               except NormalizeError:
                   continue
           if normalized == 0:
               raise HTTPException(422, "No valid rows found — check EXPORT_SCHEMA.md columns")
           source.path.parent.mkdir(parents=True, exist_ok=True)
           tmp.replace(source.path)  # atomic swap only after validation passes
       finally:
           tmp.unlink(missing_ok=True)
       return {"ok": True, "rows_valid": normalized, "rows_total": len(rows)}
   ```
2. **`webapp/static/index.html`** — an "Upload data" panel with two file inputs (App Store CSV, Play Store CSV) next to the existing "Refresh data" button.
3. **`webapp/static/app.js`** — `FormData` + `fetch(..., {method:'POST', body: formData})` per file, then call the existing `loadDashboard()` again on success.

### Design notes
- Validate-then-atomic-replace (write to a temp file, run it through the real
  loader/normalizer, only `os.replace()` over the real file if that succeeds)
  so a malformed upload can never corrupt the last-known-good dataset.
- This still writes to local disk — fine on Render's persistent-during-uptime
  filesystem, but remember uploads won't survive a redeploy (same caveat as
  the OAuth token issue on the MCP server). For anything that must survive
  redeploys, pair this with object storage (S3/R2) instead of local disk.
- No new dependency needed — FastAPI's `UploadFile` is already available via `python-multipart`, which needs adding to `requirements.txt`.

### Exit criteria
- [ ] Operator can upload a CSV from the browser and see the dashboard reflect it within seconds
- [ ] A malformed upload is rejected with a clear error and never overwrites existing data
- [ ] `python-multipart` added to `requirements.txt`

---

## 6. Option C — Official Developer APIs (production-grade, automatic)

Only possible if you (or your employer) actually administer the app in both
consoles. This is the "real" production answer — no manual export step at all,
runs on a schedule.

### 6.1 Google Play Developer API

- **Auth:** a Google Cloud service account with the `reviews.readonly` (or
  broader Android Publisher) scope, granted access in Play Console → **Setup →
  API access**. Credentials are a downloaded service-account JSON key.
- **Call:** `reviews.list` on the Android Publisher API
  (`androidpublisher.googleapis.com`), paginated, filtered by
  `translationLanguage`/`startIndex` as needed.
- **New file:** `src/ingest/sources/play_store_api.py` — fetches reviews via
  `google-api-python-client`, maps each item to the canonical CSV columns, and
  writes `data/raw/play_store_reviews.csv` (or writes canonical `Review`
  objects directly and skips the CSV round-trip entirely).

**Field mapping** (Play Developer API `Review`/`ReviewReplyResult` → this project's schema):

| Play API field | → | `EXPORT_SCHEMA.md` column |
|---|---|---|
| `reviewId` | → | `review_id` |
| `comments[0].userComment.starRating` | → | `rating` |
| *(Play reviews have no separate title)* | → | `title` (leave empty) |
| `comments[0].userComment.text` | → | `text` |
| `comments[0].userComment.lastModified.seconds` (epoch) | → | `date` (convert to ISO date) |
| `comments[0].userComment.reviewerLanguage` | → | `language` (optional) |
| *(never map)* `authorName`-equivalent fields | — | dropped — Play's public review objects don't expose reviewer PII by default, but strip defensively anyway |

### 6.2 App Store Connect API

- **Auth:** an App Store Connect API key (Issuer ID + Key ID + `.p8` private
  key) generated in App Store Connect → **Users and Access → Integrations**.
  Requests are signed as a short-lived JWT (no static bearer token).
- **Call:** `GET /v1/apps/{id}/customerReviews`, paginated via `links.next`.
- **New file:** `src/ingest/sources/app_store_api.py` — signs the JWT
  (`PyJWT` + the `.p8` key), calls the endpoint, maps to canonical columns.

**Field mapping** (App Store Connect API `customerReviews` → this project's schema):

| App Store Connect field | → | `EXPORT_SCHEMA.md` column |
|---|---|---|
| `id` | → | `review_id` |
| `attributes.rating` | → | `rating` |
| `attributes.title` | → | `title` |
| `attributes.body` | → | `text` |
| `attributes.createdDate` (ISO 8601) | → | `date` |
| `attributes.territory` | → | `territory` |
| *(never map)* `attributes.reviewerNickname` | — | dropped — this is a public display handle, not real PII, but still excluded per the existing "no identity fields" rule |

### 6.3 Wiring into the existing pipeline

Two ways to plug these in, in increasing order of integration depth:

1. **Cheapest:** a small scheduled script (`scripts/fetch_real_reviews.py`)
   that calls both new source modules and overwrites `data/raw/*.csv`, then
   the existing `python -m src.ingest.cli` (etc.) runs exactly as today. Zero
   changes to `src/ingest/*`.
2. **Cleaner:** add a `source_type: api | csv` field per store in
   `config/pulse.yaml`, and branch in `src/ingest/pipeline.py`'s `ingest()`
   to call the API fetcher instead of `load_rows(source.path)` when
   `source_type: api`. More invasive, but avoids the CSV round-trip and the
   "stale file on disk" question entirely.

### 6.4 Scheduling

Render has a **Cron Job** resource type (separate from a Web Service) that can
run `python scripts/fetch_real_reviews.py` on a schedule (e.g. daily) and
either (a) commit the refreshed CSVs back via a git push from CI, or (b) write
straight to a shared volume / object storage that `webapp/`'s Web Service also
reads from. Given Render's free-tier services don't share a filesystem, (b)
generally means adding S3/R2 or a small Postgres table as the shared store —
worth calling out explicitly as the next architecture decision if you go this
route.

### 6.5 Credentials handling

- Google service-account JSON → store as a Render **Secret File**, not an
  env var (it's a multi-line JSON blob) — reference its path via
  `GOOGLE_APPLICATION_CREDENTIALS`.
- App Store Connect `.p8` key → same treatment, plus `APP_STORE_ISSUER_ID` /
  `APP_STORE_KEY_ID` as regular env vars.
- Add both to `.gitignore` explicitly (`*.p8`, `service-account*.json`) even
  though `.env`-style secrets are already excluded — these are file-based
  secrets, a different mistake pattern than a `.env` leak.

### Exit criteria
- [ ] `src/ingest/sources/play_store_api.py` fetches real reviews and writes rows the existing normalizer accepts unmodified
- [ ] `src/ingest/sources/app_store_api.py` does the same for App Store Connect
- [ ] Credentials are Render Secret Files / env vars, never committed
- [ ] A scheduled job refreshes `data/raw/*.csv` (or bypasses the CSV step) without manual steps
- [ ] Existing Phase 1 exit criteria still hold unchanged (window filtering, dedup, no scrape) — because nothing in `src/ingest/loader.py`/`normalize.py`/`pipeline.py` needed to change

---

## 7. Suggested order to actually build this

| Step | What | Unlocks |
|---|---|---|
| 1 | Option A once, manually, for one real app | Prove the existing pipeline/dashboard work unmodified on real data |
| 2 | Option B (upload endpoint) | Non-engineers can refresh data without git/SSH access |
| 3 | Option C, Play Store only (Google's API is simpler — one JSON key, no JWT signing) | First fully automated store |
| 4 | Option C, App Store | Both stores automated |
| 5 | Render Cron Job + shared storage decision | Real "runs itself weekly" production posture |

## 8. What does *not* need to change

- `src/models.py`, `src/ingest/normalize.py`, `src/ingest/window.py`, `src/privacy/*`, `src/analysis/*`, `src/compose/*` — all already store/source-agnostic.
- `webapp/data.py`, `webapp/categorize.py` — already operate on whatever `ingest()` returns.
- The Docs/Gmail MCP delivery path (Phase 5-6) — unaffected by where reviews came from.

This is the main point worth making in an interview: **the ingestion boundary
was designed from Phase 1 onward to be swappable** (public CSV/JSON in, canonical
`Review` objects out) specifically so real data sources could be added later
without touching privacy, analysis, compose, or delivery.
