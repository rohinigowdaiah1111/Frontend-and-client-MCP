"""
Review Pulse Console — real backend (problemStatement.md, implementationPlan.md).

Replaces the earlier static Stitch mockup: this actually reads data/raw,
classifies reviews (payment issue / KYC issue / positive feedback / other),
charts them, and wires the existing Phase 4b (Groq) + Phase 5-6 (Docs/Gmail
MCP) pipeline behind three buttons in the UI.

Gmail stays draft-only by design — see src/adapters/gmail_mcp.py and
implementationPlan.md's "Out of Scope: Auto-sending email". The "Create Draft"
endpoint below only ever calls gmail_create_draft, never a send tool.

Run locally:
    uvicorn webapp.app:app --reload --port 8000
Then open http://localhost:8000/
"""

from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.adapters.mcp_client import McpToolError, call_mcp_tool
from src.compose.delivery_gate import DeliveryBlocked, fill_doc_link, require_delivery_ready
from src.compose.facts import load_fact_pack
from src.compose.groq_writer import GroqWriteError, write_final_copy
from src.compose.render import load_week_of, render_pattern
from src.config import load_config
from webapp.auth import (
    SESSION_COOKIE,
    auth_enabled,
    check_password,
    create_session,
    destroy_session,
    require_session,
)
from webapp.data import build_dashboard

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("webapp")

app = FastAPI(title="Groww Review Pulse API")

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _mcp_server_url() -> str:
    base = os.environ.get("MCP_SERVER_URL", "").rstrip("/")
    if not base:
        raise HTTPException(status_code=500, detail="MCP_SERVER_URL is not set in the environment")
    return f"{base}/mcp"


def _mcp_auth_token() -> str:
    token = os.environ.get("MCP_AUTH_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="MCP_AUTH_TOKEN is not set in the environment")
    return token


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "auth_required": auth_enabled()}


class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
def login(req: LoginRequest, response: Response) -> dict[str, Any]:
    if not check_password(req.password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    token = create_session()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 12,  # 12h
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(
    response: Response, rpc_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)
) -> dict[str, Any]:
    destroy_session(rpc_session)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/dashboard", dependencies=[Depends(require_session)])
def dashboard() -> dict[str, Any]:
    """Phases 1-3 live: raw reviews -> anonymized -> theme-tagged + categorized."""
    try:
        return build_dashboard()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to build dashboard")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/compose", dependencies=[Depends(require_session)])
def compose() -> dict[str, Any]:
    """Phase 4b: Groq writes the final report + email from the current fact pack."""
    cfg = load_config()
    facts_path = cfg.root / "output" / "pulse-facts.json"
    if not facts_path.is_file():
        build_dashboard(cfg)  # first run: produce pulse-facts.json before composing
    fact_pack = load_fact_pack(facts_path)
    try:
        copy, report = write_final_copy(fact_pack, config=cfg)
    except GroqWriteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "ok": report.ok,
        "report_markdown": copy.report_markdown,
        "email_subject": copy.email.subject,
        "email_body": copy.email.body,
        "model": copy.model,
        "word_count": copy.word_count,
    }


class PublishDocRequest(BaseModel):
    text: str | None = None  # optional override; defaults to the Groq report


@app.post("/api/deliver/doc", dependencies=[Depends(require_session)])
async def deliver_doc(req: PublishDocRequest) -> dict[str, Any]:
    """Phase 5: append the Groq report to the configured Google Doc via MCP."""
    cfg = load_config()
    doc_id = os.environ.get("DOCS_PULSE_DOCUMENT_ID", "")
    if not doc_id:
        raise HTTPException(status_code=500, detail="DOCS_PULSE_DOCUMENT_ID is not set in the environment")

    try:
        gate = require_delivery_ready(cfg)
    except DeliveryBlocked as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    text = (req.text if req.text is not None else gate.report_body) or ""
    if not text.strip():
        raise HTTPException(status_code=422, detail="Nothing to publish — report is empty")

    body = f"\n\n---\n\n{text.strip()}\n"
    try:
        result_text = await call_mcp_tool(
            server_url=_mcp_server_url(),
            auth_token=_mcp_auth_token(),
            tool_name="docs_append_text",
            arguments={"documentId": doc_id, "text": body},
        )
    except McpToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    return {"ok": True, "url": doc_url, "server_response": result_text}


class CreateDraftRequest(BaseModel):
    to: str | None = None
    subject: str | None = None
    body: str | None = None
    doc_url: str | None = None


@app.post("/api/deliver/draft", dependencies=[Depends(require_session)])
async def deliver_draft(req: CreateDraftRequest) -> dict[str, Any]:
    """Phase 6: create a Gmail DRAFT via MCP — never sends (see module docstring)."""
    cfg = load_config()
    try:
        gate = require_delivery_ready(cfg)
    except DeliveryBlocked as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    assert gate.email is not None

    to_addr = req.to or cfg.delivery.gmail_to
    week_of = load_week_of(cfg.root / "output")
    subject = req.subject or gate.email.subject or render_pattern(
        cfg.delivery.gmail_subject_pattern, week_of=week_of or date.today()
    )
    body = req.body if req.body is not None else fill_doc_link(gate.email.body, req.doc_url)

    try:
        result_text = await call_mcp_tool(
            server_url=_mcp_server_url(),
            auth_token=_mcp_auth_token(),
            tool_name="gmail_create_draft",
            arguments={"to": [to_addr], "subject": subject, "body": body},
        )
    except McpToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"ok": True, "server_response": result_text}


# Mounted last so /api/* routes above take precedence over the static catch-all.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
