# Review Pulse Console (real functional app)

A live FastAPI backend + single-page dashboard that replaces the earlier static
Stitch mockup (`stitch_review_pulse_console/`) with an app that actually:

1. Reads real reviews from `data/raw/` and classifies each one into **Payment
   issue / KYC issue / Onboarding issue / Statement issue / Withdrawal issue /
   Positive feedback / Other** (`webapp/categorize.py`, on top of Phase 3's
   theme clustering).
2. Charts the category breakdown and lists the underlying reviews, filterable
   by category.
3. Has a message box: **Generate report + email (Groq)** runs Phase 4b live
   and shows the editable report + email.
4. **Publish to Google Doc** appends that report to the configured Doc via the
   Docs MCP tool (Phase 5).
5. **Create Gmail draft** creates a Gmail draft via the Gmail MCP tool (Phase
   6) — this **never sends**. There is no send/auto-send button anywhere;
   drafts land in Gmail's Drafts folder for a human to review and send
   manually, per `implementationPlan.md`'s non-goals.

## Architecture

```
webapp/
  app.py          FastAPI app: /api/dashboard, /api/compose, /api/deliver/doc, /api/deliver/draft
  data.py         Ingest -> privacy -> theme-cluster (reuses src/ as-is) + categorize
  categorize.py   Per-review category derivation (positive vs. per-theme issue)
  static/         Vanilla JS/HTML frontend (Tailwind + Chart.js via CDN, no build step)
src/adapters/
  mcp_client.py   Standalone Python MCP client (Streamable HTTP) — lets this backend
                  call the Docs/Gmail MCP server directly, without going through
                  Cursor's built-in MCP client.
```

The frontend is served by the same FastAPI process (`StaticFiles` mount), so
there's a single deployable service and no CORS to configure.

## Run locally

```bash
pip install -r requirements.txt
uvicorn webapp.app:app --reload --port 8000
```

Open http://localhost:8000/. Requires the same `.env` as the rest of the
pipeline (`GROQ_API_KEY`, `MCP_SERVER_URL`, `MCP_AUTH_TOKEN`,
`DOCS_PULSE_DOCUMENT_ID`, `GMAIL_DRAFT_TO` — see `.env.example`).

## Deploy

Because this is a long-running server (not a static bundle), deploy it like
the MCP server itself — as a Render **Web Service**, not on Vercel:

1. Push this repo to GitHub (already done).
2. Render dashboard → New → Web Service → pick this repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn webapp.app:app --host 0.0.0.0 --port $PORT`
5. Add the same environment variables as `.env` (`GROQ_API_KEY`,
   `MCP_SERVER_URL`, `MCP_AUTH_TOKEN`, `DOCS_PULSE_DOCUMENT_ID`,
   `GMAIL_DRAFT_TO`) under Render's Environment tab — never commit `.env`.
6. Deploy. The dashboard, Groq compose, Doc publish, and Gmail draft buttons
   all work from the resulting URL.

## Known limitations

- **Google OAuth on Render's free tier is ephemeral.** If the MCP server
  (`mcp-server-ziee.onrender.com`) has been asleep, `/api/deliver/doc` and
  `/api/deliver/draft` will return a `REAUTH_REQUIRED` error until you
  re-visit `https://<mcp-server>/authorize?token=<MCP_AUTH_TOKEN>` in a
  browser. This is a property of the MCP server's hosting, not this app.
- **No auth in front of this app yet.** Add a password gate (or Render's own
  access controls) before pointing it at real, non-sample review data.
- **`data/raw/*.csv` is the data source.** To classify different data, replace
  those two CSVs (same columns) and hit "Refresh data" — there's no upload UI
  yet.
