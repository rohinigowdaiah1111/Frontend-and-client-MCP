# Deployment: Review Pulse Console (Vercel)

## What this is

Static HTML/Tailwind screens generated in Stitch for the **Review Pulse Console** — an internal ops/monitoring dashboard for the Weekly Mobile-Store Review Pulse pipeline described in `../architecture.md` and `../implementationPlan.md`. It visualizes:

- Phase 3's `PulsePayload` (themes, quotes, actions) — `architecture.md` §5
- Phase 4b's Groq final report + final email — `implementationPlan.md` Phase 4b
- Phase 5–6's Google Docs / Gmail delivery status — `implementationPlan.md` Phases 5–6
- The Phase 0 MCP inventory / connection health checklist — `docs/phase0/MCP_INVENTORY.md`

**This console does not call the real pipeline yet.** Every number, theme, quote, and status pill in these screens is Stitch-generated sample content shaped to match the data model in `architecture.md` §5 (`Review`, `Theme`, `PulsePayload`, `PulseDocument`, `EmailDraft`) — not a live read of `output/*.json`. See "Known limitations" below for what wiring it up for real would take.

## Current state (pre-deploy)

5 standalone static screens. No build step, no framework, no `package.json`:

| Screen | File | Maps to |
|---|---|---|
| Dashboard | `dashboard_home/code.html` | Phase 3 top themes + Phase 4b report/email status + Phase 5–6 delivery pills |
| Theme Explorer | `theme_explorer/code.html` | Phase 3 Theme Clusterer (all ≤5 themes) |
| Report Preview | `report_preview/code.html` | Phase 4b Groq final report + final email + post-LLM validation badges |
| Run History | `run_history/code.html` | Phase 7 "run metrics log" |
| Settings | `settings/code.html` | `config/pulse.yaml` surface + Phase 0 MCP connection health |

Design tokens (colors, type, spacing) are documented in `review_pulse_console/DESIGN.md`. Each screen is fully self-contained: Tailwind is loaded via the CDN build (`cdn.tailwindcss.com`), fonts (Inter, Geist, Material Symbols) load over HTTPS from Google Fonts — no local assets, no environment variables, no server-side code, and (confirmed) **no secrets** embedded anywhere in the HTML.

## What was added for deployment

- **`vercel.json`** (project root, alongside this file) — adds clean, human-readable routes that rewrite to the existing `*/code.html` files, without moving or renaming anything Stitch generated:

  | Route | Rewrites to |
  |---|---|
  | `/` | `dashboard_home/code.html` |
  | `/dashboard` | `dashboard_home/code.html` |
  | `/theme-explorer` | `theme_explorer/code.html` |
  | `/report-preview` | `report_preview/code.html` |
  | `/run-history` | `run_history/code.html` |
  | `/settings` | `settings/code.html` |

  Without this file, Vercel would still deploy successfully (it serves any static file tree with zero config), but each screen would only be reachable at its raw path (e.g. `/dashboard_home/code.html`).

## Deploy steps

### Option A — Vercel Dashboard (recommended; no local CLI needed)

1. Push this folder to a GitHub repo Vercel can access — e.g. the same repo already used for the backend, [`rohinigowdaiah1111/Frontend-and-client-MCP`](https://github.com/rohinigowdaiah1111/Frontend-and-client-MCP), or a dedicated frontend repo if you'd rather keep them separate.
2. In the Vercel dashboard: **Add New… → Project → Import** the repo.
3. **Root Directory**: set to `stitch_review_pulse_console` (so Vercel only deploys this static site, not the Python pipeline alongside it).
4. **Framework Preset**: `Other` — no framework should be auto-detected, and that's expected/correct.
5. **Build Command**: leave empty ("No Build Command").
6. **Output Directory**: leave as `.` (the root directory selected in step 3).
7. Click **Deploy**. Vercel serves the static files as-is; `vercel.json`'s rewrites apply automatically on every deploy.

### Option B — Vercel CLI

```bash
npm i -g vercel
cd stitch_review_pulse_console
vercel login
vercel        # first deploy -> preview URL; accept "Other" framework, no build command, output dir "."
vercel --prod # promote to the production URL once the preview looks right
```

## Post-deploy checklist

- [ ] `/` and `/dashboard` load the Dashboard screen
- [ ] `/theme-explorer`, `/report-preview`, `/run-history`, `/settings` each load their respective screen
- [ ] Material Symbols icons and Inter/Geist fonts render correctly (loaded from `fonts.googleapis.com` — no Vercel config needed, but verify nothing in your network blocks it)
- [ ] Dark mode class toggle (`html.dark`) doesn't break layout, on screens where it's wired
- [ ] No secrets present in the deployed bundle — re-confirmed here: no `GROQ_API_KEY`, `MCP_AUTH_TOKEN`, or Google credentials anywhere in these static files; they were never meant to hold any

## Known limitations / next steps

- **Static mock data only.** Wiring this to the real pipeline would mean either:
  - a small Vercel serverless function that reads `output/pulse-facts.json`, `output/pulse-latest.md`, `output/email-latest.json`, and `output/groq-meta.json` from wherever the pipeline's `output/` directory is reachable, or
  - a static JSON fetch if those files get published somewhere the frontend can reach after each run (e.g. committed back to the repo, or served from a tiny API in front of the pipeline).
- ~~Sidebar nav links are placeholders (`href="#"`)~~ — **fixed**: all 5 screens now link to the real routes (`/dashboard`, `/theme-explorer`, `/report-preview`, `/run-history`, `/settings`) declared in `vercel.json`, with the current page's link kept visually active. Verified across all 25 nav entries (5 screens × 5 items).
- **No auth in front of this yet.** Since it's meant to show internal pipeline data (even if only samples today), add Vercel's built-in password protection (Pro plan) or another auth gate before ever pointing it at real review data — consistent with the pipeline's "no PII, internal-only" posture in `architecture.md` §9.
