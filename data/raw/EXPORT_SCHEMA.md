# Public Review Export Schemas

Expected columns for loaders (Phase 1). Use **public** store exports only—no login scraping.

Replace sample CSVs with your product’s public exports; keep column names or update alias maps in the loader.

---

## App Store (`app_store_reviews.csv`)

| Column | Required | Notes |
|--------|----------|-------|
| `review_id` | yes | Stable export key (no PII) |
| `rating` | no | Integer 1–5 |
| `title` | no | Review title |
| `text` | yes* | Body; or title if body empty |
| `date` | yes | ISO date `YYYY-MM-DD` or parseable datetime |
| `app_version` | no | Ignored by pulse unless needed later |
| `territory` | no | Optional |

\* At least one of `title` / `text` must be non-empty after trim.

**Aliases accepted later:** `review`, `body`, `content` → `text`; `star`, `stars` → `rating`; `created_date`, `review_date` → `date`.

---

## Play Store (`play_store_reviews.csv`)

| Column | Required | Notes |
|--------|----------|-------|
| `review_id` | yes | Stable export key (no PII) |
| `rating` | no | Integer 1–5 |
| `title` | no | Often empty on Play |
| `text` | yes* | Review body |
| `date` | yes | ISO date `YYYY-MM-DD` or parseable datetime |
| `app_version` | no | Optional |
| `language` | no | Optional |

\* Same rule as App Store.

**Do not include** in exports fed to the pipeline (or map away): `username`, `author`, `email`, `device_id`, `reviewer_name`.

---

## Window

Loaders keep reviews within `window_weeks` from `config/pulse.yaml` (8–12). Sample files use dates from ~May–Jul 2026 so a 10-week window from 2026-07-28 includes them.

---

## Product filter

If an export mixes apps, add `package_name` / `app_id` and configure a filter in Phase 1. Samples are single-product.
