"""Render Docs title / Gmail subject patterns (`{iso_week}`, `{week_of}`) for Phase 5–6."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def iso_week_label(d: date) -> str:
    """e.g. date(2026, 7, 28) -> '2026-W31'."""
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def render_pattern(pattern: str, *, week_of: date) -> str:
    return pattern.replace("{iso_week}", iso_week_label(week_of)).replace(
        "{week_of}", week_of.isoformat()
    )


def load_week_of(output_dir: Path) -> date | None:
    """Read week_of from the Phase 3 fact pack, if present."""
    facts_path = output_dir / "pulse-facts.json"
    if not facts_path.is_file():
        return None
    try:
        data = json.loads(facts_path.read_text(encoding="utf-8"))
        raw = data.get("week_of")
        if raw:
            return date.fromisoformat(raw)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return None
