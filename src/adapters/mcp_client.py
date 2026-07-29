"""
Standalone MCP client bridge (architecture §8 DocsPort/MailPort transport).

Calls the deployed Gmail/Docs MCP server (docs/phase0/MCP_INVENTORY.md) directly
over Streamable HTTP, without going through Cursor's built-in MCP client. This is
what `webapp/` uses so the dashboard's "Publish to Doc" / "Create Draft" buttons
work from a plain running server process, not just inside the IDE.

Auth model unchanged from the rest of this project: MCP_AUTH_TOKEN is a shared
bearer secret gating the whole /mcp endpoint (see .env.example); the server's own
Google OAuth state (its own /authorize flow) is independent of this client and
lives entirely on the MCP server's host.
"""

from __future__ import annotations

from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class McpToolError(RuntimeError):
    """Raised when an MCP tool call fails (transport error or isError=True)."""


def flatten_exceptions(exc: BaseException) -> list[BaseException]:
    """Recursively unwrap nested BaseExceptionGroups down to their leaf exceptions.

    `call_mcp_tool` raises through several anyio TaskGroups (streamable_http_client,
    ClientSession), each of which can add its own ExceptionGroup layer, so even an
    `except* McpToolError` catch can still hand back a group-within-a-group. Use
    this to get the real leaf message(s) for logging/HTTP error bodies.
    """
    if isinstance(exc, BaseExceptionGroup):
        out: list[BaseException] = []
        for sub in exc.exceptions:
            out.extend(flatten_exceptions(sub))
        return out
    return [exc]


def _looks_like_error(text: str) -> bool:
    """This server (rohinigowdaiah1111/MCP-server) sometimes returns business-logic
    failures (e.g. REAUTH_REQUIRED) as a plain "Error [...]" text block without
    setting isError=True, so isError alone can't be trusted."""
    return text.strip().lower().startswith("error")


async def call_mcp_tool(
    *,
    server_url: str,
    auth_token: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout: float = 60.0,
) -> str:
    """
    Call a single MCP tool over Streamable HTTP and return its concatenated text content.

    `server_url` must be the full `/mcp` endpoint (e.g. f"{MCP_SERVER_URL}/mcp").
    Raises McpToolError on transport failure or when the tool itself reports isError.
    """
    # NOTE: streamable_http_client/ClientSession run their I/O inside anyio
    # TaskGroups, so any exception raised anywhere in this function's body
    # (including this one) reaches the caller wrapped in a BaseExceptionGroup.
    # Callers must catch with `except*`, not a plain `except McpToolError`.
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with httpx2.AsyncClient(headers=headers, timeout=timeout) as http_client:
        async with streamable_http_client(server_url, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                texts = [block.text for block in result.content if hasattr(block, "text")]
                text = "\n".join(texts).strip()
                if getattr(result, "isError", False) or _looks_like_error(text):
                    raise McpToolError(text or f"{tool_name} failed with no error detail")
                return text
