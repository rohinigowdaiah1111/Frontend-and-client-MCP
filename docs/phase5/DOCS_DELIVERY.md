# Phase 5 — Google Docs via MCP

Publishes the **Groq final report** (`output/pulse-latest.md`) to Google Docs. The MCP tool call is intentionally not wired yet (no Docs MCP server selected in `docs/phase0/MCP_INVENTORY.md`); everything around the call — gating, title rendering, update-vs-create — is implemented so wiring the real tool is a small change confined to `DocsMcpAdapter.create_or_update_doc` / `get_doc_link`.

## Gate

`publish_groq_report()` calls `require_delivery_ready()` (from `src/compose/delivery_gate.py`) before doing anything else. `create_or_update_doc()` re-checks the same gate defensively, so even a direct call bypassing `publish_groq_report()` cannot reach MCP without a successful Phase 4b run.

## Title rendering

`delivery.docs_title_pattern` (default `Weekly Review Pulse — {iso_week}`) is rendered against the **real** week using `src/compose/render.py`:

- `iso_week_label(date)` → `2026-W31`
- `week_of` is read from `output/pulse-facts.json` (Phase 3's `week_of` field); falls back to today if the fact pack is missing.

Call `DocsMcpAdapter().render_title()` directly to preview the title without publishing.

## Update vs. create (D-04)

`output/docs-meta.json` caches the last `{title, doc_id, url}`. On the next `publish_groq_report()`:

- If the rendered title matches the cached title (same ISO week), the cached `doc_id` is passed through as `existing_doc_id` — once the real MCP tool is wired, this should call its *update* path instead of creating a duplicate Doc.
- Otherwise (new week, or no cache yet) `existing_doc_id` is `None` and a new Doc is created.

This is plumbing only until a real tool exists — `create_or_update_doc()` still raises `NotImplementedError`, but the message reports whether it *would* have updated or created, and which `doc_id` it would have used.

## Wiring the real tool

1. Pick a Docs MCP server (`docs/phase0/MCP_INVENTORY.md`) and set `DocsMcpAdapter.SERVER_ID`, `TOOL_CREATE_OR_UPDATE`, `TOOL_GET_LINK`.
2. Replace the `raise NotImplementedError(...)` body of `create_or_update_doc()` with the actual MCP tool call, branching on `existing_doc_id` for update vs. create.
3. On success, call `self._save_doc_cache(out, title, result)` (already done by `publish_groq_report()` once `create_or_update_doc()` returns).
4. Add transient-error retry around the tool call; on repeated failure, propagate the error rather than reporting success (never invent a Doc URL).

## Modules

| Module | Role |
|--------|------|
| `src/adapters/docs_mcp.py` | `DocsPort`, `DocsMcpAdapter`, doc-id cache |
| `src/compose/render.py` | Title/subject pattern rendering |
| `src/compose/delivery_gate.py` | Pre-MCP gate (Groq artifacts must exist and be valid) |
