"""Persist and load pulse fact packs for Groq."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_fact_pack(fact_pack: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fact_pack, indent=2) + "\n", encoding="utf-8")
    return path


def load_fact_pack(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_quotes(fact_pack: dict[str, Any]) -> list[str]:
    quotes = fact_pack.get("quotes") or []
    out: list[str] = []
    for item in quotes:
        if isinstance(item, dict):
            text = item.get("text")
            if text:
                out.append(str(text))
        elif isinstance(item, str) and item.strip():
            out.append(item)
    return out
