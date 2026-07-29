"""Minimal shared-password gate for the Review Pulse Console.

This is an internal ops tool that can show real (anonymized) review data and
trigger real Docs/Gmail MCP calls, so it should not be left open once it's
pointed at anything beyond sample data (see implementationPlan.md Phase 10 —
"add an auth gate before showing real review data").

Deliberately simple: one shared password (WEBAPP_PASSWORD), no user accounts.
Sessions are opaque tokens held in memory, so they reset on every restart —
acceptable for a small internal tool, not meant to survive a redeploy.
"""

from __future__ import annotations

import hmac
import os
import secrets

from fastapi import Cookie, HTTPException

SESSION_COOKIE = "rpc_session"
_valid_sessions: set[str] = set()


def _configured_password() -> str | None:
    return os.environ.get("WEBAPP_PASSWORD") or None


def auth_enabled() -> bool:
    """No WEBAPP_PASSWORD set -> gate is off (e.g. local dev)."""
    return _configured_password() is not None


def check_password(candidate: str) -> bool:
    expected = _configured_password()
    if not expected:
        return True
    return hmac.compare_digest(candidate, expected)


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _valid_sessions.add(token)
    return token


def destroy_session(token: str | None) -> None:
    if token:
        _valid_sessions.discard(token)


def require_session(rpc_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> None:
    """FastAPI dependency: raise 401 unless the gate is off or the cookie is a known session."""
    if not auth_enabled():
        return
    if rpc_session is None or rpc_session not in _valid_sessions:
        raise HTTPException(status_code=401, detail="Login required")
