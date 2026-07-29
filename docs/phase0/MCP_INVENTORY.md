# MCP Inventory — Docs & Gmail

Phase 0 task: identify Google Docs and Gmail MCP servers and note tool names for create/update Doc and create draft.

**Auth rule:** Credentials and OAuth live in the **MCP host configuration** (Cursor MCP servers). Application source only calls tools via adapters—no bespoke Google API clients.

---

## Environment scan (2026-07-28, updated 2026-07-29)

| Server | Present? | Notes |
|--------|----------|--------|
| Google Docs MCP | **Candidate identified, not yet registered** | [`rohinigowdaiah1111/MCP-server`](https://github.com/rohinigowdaiah1111/MCP-server) — deployed and reachable at `https://mcp-server-ziee.onrender.com` (`GET /health` → `{"status":"ok"}`), but not yet added to Cursor's `mcp.json`, so it doesn't appear in `GetMcpTools` yet |
| Gmail MCP | **Candidate identified, not yet registered** | Same server as above — it's a combined Gmail + Google Docs MCP server |
| `user-alphavantage` | Yes | Unrelated to pulse delivery |
| `user-github` | Yes | Unrelated to pulse delivery |

Pattern search for `gmail|docs|google|drive` returned **no matches** as of 2026-07-28 (before this server was registered in Cursor's MCP config). Re-run `GetMcpTools` after adding it to confirm it's live in this workspace.

---

## Logical ports (architecture §8)

Adapters in `src/adapters/` implement these ports; map to concrete tool names once servers are installed.

**Prerequisite:** `src/compose/delivery_gate.py` must allow delivery — Groq final report + email already written (`require_before_delivery`).

### DocsPort

| Method | Intent | Expected MCP capability |
|--------|--------|-------------------------|
| `createOrUpdateDoc(title, body)` | Create/update Doc with **Groq final report** | create/update document |
| `getDocLink(docId)` | Shareable URL for email | get document / export link |
| `publish_groq_report(title)` | Gate + publish `pulse-latest.md` | same |

### MailPort

| Method | Intent | Expected MCP capability |
|--------|--------|-------------------------|
| `createDraft({ to, subject, body })` | Draft only — **never send** | create draft message |
| `create_draft_from_groq(doc_url)` | Gate + draft from Groq email | same |

---

## Related secrets

| Secret | Where |
|--------|--------|
| Google OAuth (Gmail + Docs scopes) | Held by the `gmail-docs` MCP server itself (encrypted token file on its Render host), obtained via its `/authorize` flow — never in this repo |
| `MCP_AUTH_TOKEN` | Shared bearer secret for the `gmail-docs` server's remote `/mcp` endpoint — lives in Cursor's `mcp.json` header config for that server, not in `config/pulse.yaml` or `.env` here |
| `GROQ_API_KEY` | Environment / `.env` (see `.env.example`) — used in Phase 4b, not MCP |

---

## Operator setup (unblock Phases 5–6)

1. Register the identified server in Cursor's MCP config (`mcp.json`), e.g.:
   ```json
   {
     "mcpServers": {
       "gmail-docs": {
         "url": "https://mcp-server-ziee.onrender.com/mcp",
         "headers": { "Authorization": "Bearer <MCP_AUTH_TOKEN>" }
       }
     }
   }
   ```
   (`MCP_AUTH_TOKEN` is the shared secret configured on the Render deployment, not a value this repo generates.)
2. Complete Google OAuth/consent via the server's own `/authorize?token=<MCP_AUTH_TOKEN>` endpoint (remote equivalent of the repo's `npm run authorize`) — not in this repo, and not a bespoke Google client here.
3. Re-run tool discovery (`GetMcpTools`) to confirm the server and its tools are now visible in this workspace.
4. Update adapter mappings in `src/adapters/docs_mcp.py` and `src/adapters/gmail_mcp.py` per the table below.

### Tool name worksheet

| Port method | Server id | Tool name | Smoke result |
|-------------|-----------|-----------|--------------|
| `createOrUpdateDoc` (create path) | `gmail-docs` | `docs_create` | `/health` OK; not yet smoke-tested via MCP (server not registered in this workspace yet) |
| `createOrUpdateDoc` (update path) | `gmail-docs` | `docs_append_text` (append-only — no true overwrite tool exists; see `implementationPlan.md` Phase 5 design decision) | _pending_ |
| `getDocLink` | — | *(no MCP tool — URL is deterministic: `https://docs.google.com/document/d/{documentId}/edit`, also returned by `docs_create`/`docs_append_text`)* | n/a |
| `createDraft` | `gmail-docs` | `gmail_create_draft` (note: tool's `to` param is an array of emails, not a single string) | _pending_ |

**Do not wire:** `gmail_send_email`, `gmail_send_draft` — this server supports sending, but the pipeline's non-goal ("no auto-send", edge-case M-03) means `GmailMcpAdapter` must never call either.

**Smoke checklist**

- [ ] Docs MCP server listed by host — server identified and reachable over HTTP; not yet added to `mcp.json`
- [ ] Gmail MCP server listed by host — same server, same status
- [ ] List tools succeeds for both
- [ ] Draft-create tool exists; send tool is **not** wired in adapters — send tools exist on this server and must be deliberately avoided (see guardrail task added to Phase 6)

---

## Non-goals

- Do not add `google-api-python-client` / OAuth client code as the primary integration path.
- Do not store `credentials.json` / `token.json` in the repo (see `.gitignore`).
