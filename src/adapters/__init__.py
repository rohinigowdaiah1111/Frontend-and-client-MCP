"""Adapter package: MCP ports for Google Docs and Gmail (MCP-first delivery)."""

from .docs_mcp import DocResult, DocsMcpAdapter, DocsPort
from .gmail_mcp import DraftRequest, DraftResult, GmailMcpAdapter, MailPort

__all__ = [
    "DocResult",
    "DocsMcpAdapter",
    "DocsPort",
    "DraftRequest",
    "DraftResult",
    "GmailMcpAdapter",
    "MailPort",
]
