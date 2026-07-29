"""
Docs MCP adapter — logical DocsPort (architecture §8).

Publishes the **Groq final report** only after the delivery gate passes.
Title is rendered from config.delivery.docs_title_pattern + the Phase 3
fact pack's week_of (D-04 aware: caches the last doc_id/title so a same-week
rerun can prefer update over blind create once a real MCP tool is wired).
Auth stays in MCP host config — never here.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from src.compose.delivery_gate import DeliveryBlocked, require_delivery_ready
from src.compose.render import load_week_of, render_pattern
from src.config import PulseConfig, load_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocResult:
    doc_id: str
    url: str | None


class DocsPort(Protocol):
    def create_or_update_doc(self, title: str, body: str) -> DocResult: ...

    def get_doc_link(self, doc_id: str) -> str | None: ...


class DocsMcpAdapter:
    """Maps DocsPort → Google Docs MCP tools. Body must be Groq final report."""

    SERVER_ID: str | None = None
    TOOL_CREATE_OR_UPDATE: str | None = None
    TOOL_GET_LINK: str | None = None

    def __init__(self, config: PulseConfig | None = None) -> None:
        self.config = config or load_config()

    def render_title(self, *, week_of: date | None = None, output_dir: Path | None = None) -> str:
        out = output_dir or (self.config.root / "output")
        wk = week_of or load_week_of(out) or date.today()
        return render_pattern(self.config.delivery.docs_title_pattern, week_of=wk)

    def publish_groq_report(
        self,
        title: str | None = None,
        *,
        week_of: date | None = None,
        output_dir: Path | None = None,
    ) -> DocResult:
        """Gate, render title, then publish. Prefer this over calling create_or_update_doc directly."""
        out = output_dir or (self.config.root / "output")
        gate = require_delivery_ready(self.config, output_dir=out)
        assert gate.report_body is not None

        resolved_title = title or self.render_title(week_of=week_of, output_dir=out)
        cached = self._load_doc_cache(out)
        existing_doc_id = (
            cached.get("doc_id")
            if cached and cached.get("title") == resolved_title
            else None
        )  # D-04: same-week rerun prefers update once a real tool exists

        result = self.create_or_update_doc(
            resolved_title, gate.report_body, existing_doc_id=existing_doc_id
        )
        self._save_doc_cache(out, resolved_title, result)
        return result

    def create_or_update_doc(
        self,
        title: str,
        body: str,
        *,
        existing_doc_id: str | None = None,
    ) -> DocResult:
        # Defense in depth: still require gate when require_before_delivery
        try:
            require_delivery_ready(self.config)
        except DeliveryBlocked as exc:
            raise DeliveryBlocked(
                f"Docs MCP blocked until Groq final copy succeeds: {exc}"
            ) from exc

        action = "update" if existing_doc_id else "create"
        raise NotImplementedError(
            "Google Docs MCP is not configured. "
            "Install a Docs MCP server and map TOOL_* in DocsMcpAdapter "
            "(docs/phase0/MCP_INVENTORY.md). Do not add a bespoke Google OAuth client. "
            f"When wired: {action} doc (existing_doc_id={existing_doc_id!r}, title={title!r}) "
            "with body from output/pulse-latest.md (Groq final report)."
        )

    def get_doc_link(self, doc_id: str) -> str | None:
        raise NotImplementedError(
            "Google Docs MCP is not configured. See docs/phase0/MCP_INVENTORY.md."
        )

    def _doc_cache_path(self, output_dir: Path) -> Path:
        return output_dir / "docs-meta.json"

    def _load_doc_cache(self, output_dir: Path) -> dict | None:
        path = self._doc_cache_path(output_dir)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read doc cache at %s", path)
            return None

    def _save_doc_cache(self, output_dir: Path, title: str, result: DocResult) -> None:
        path = self._doc_cache_path(output_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"title": title, "doc_id": result.doc_id, "url": result.url}, indent=2)
            + "\n",
            encoding="utf-8",
        )
