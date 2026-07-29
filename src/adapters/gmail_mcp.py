"""
Gmail MCP adapter — logical MailPort (architecture §8).

Draft-create only — never wire a send tool.
Uses **Groq final email** after the delivery gate passes. Subject falls back
to config.delivery.gmail_subject_pattern rendered with the Phase 3 fact pack's
week_of when Groq did not supply one.
Auth stays in MCP host config — never here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from src.compose.delivery_gate import DeliveryBlocked, fill_doc_link, require_delivery_ready
from src.compose.render import load_week_of, render_pattern
from src.config import PulseConfig, load_config


@dataclass(frozen=True)
class DraftRequest:
    to: str
    subject: str
    body: str


@dataclass(frozen=True)
class DraftResult:
    draft_id: str


class MailPort(Protocol):
    def create_draft(self, request: DraftRequest) -> DraftResult: ...


class GmailMcpAdapter:
    """Maps MailPort → Gmail MCP draft tools. Body must come from Groq email artifact."""

    SERVER_ID: str | None = None
    TOOL_CREATE_DRAFT: str | None = None
    # Intentionally no TOOL_SEND — drafts only (edge-case M-03).

    def __init__(self, config: PulseConfig | None = None) -> None:
        self.config = config or load_config()

    def create_draft_from_groq(
        self,
        *,
        doc_url: str | None = None,
        week_of: date | None = None,
        output_dir: Path | None = None,
    ) -> DraftResult:
        out = output_dir or (self.config.root / "output")
        gate = require_delivery_ready(self.config, output_dir=out)
        assert gate.email is not None

        body = fill_doc_link(gate.email.body, doc_url)
        if self.config.delivery.include_full_body and gate.report_body:
            if gate.report_body.strip() not in body:
                body = body.rstrip() + "\n\n---\n\n" + gate.report_body.strip()

        wk = week_of or load_week_of(out) or date.today()
        subject = gate.email.subject or render_pattern(
            self.config.delivery.gmail_subject_pattern, week_of=wk
        )
        return self.create_draft(
            DraftRequest(
                to=self.config.delivery.gmail_to,
                subject=subject,
                body=body,
            )
        )

    def create_draft(self, request: DraftRequest) -> DraftResult:
        try:
            require_delivery_ready(self.config)
        except DeliveryBlocked as exc:
            raise DeliveryBlocked(
                f"Gmail MCP blocked until Groq final copy succeeds: {exc}"
            ) from exc

        raise NotImplementedError(
            "Gmail MCP is not configured. "
            "Install a Gmail MCP server and map TOOL_CREATE_DRAFT in GmailMcpAdapter "
            "(docs/phase0/MCP_INVENTORY.md). Do not add a bespoke Google OAuth client. "
            "Never call a send tool from this adapter. "
            "When wired, draft body from output/email-latest.json (Groq final email)."
        )
