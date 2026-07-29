"""Review Loader — public CSV/JSON exports only (no scrape/login)."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)


class LoaderError(RuntimeError):
    """Entire file cannot be read."""


def _read_text_with_fallback(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning("UTF-8 decode failed for %s; retrying latin-1", path)
        return path.read_text(encoding="latin-1")


def load_rows(path: Path) -> list[dict[str, Any]]:
    """Load rows from a public export file (.csv or .json)."""
    if not path.is_file():
        raise FileNotFoundError(str(path))

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return list(_load_csv(path))
    if suffix == ".json":
        return list(_load_json(path))
    raise LoaderError(f"Unsupported export format: {path.suffix} (use .csv or .json)")


def _load_csv(path: Path) -> Iterator[dict[str, Any]]:
    text = _read_text_with_fallback(path)
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        return
    for row in reader:
        if row is None:
            continue
        if all((v is None or str(v).strip() == "") for v in row.values()):
            continue
        yield {k: v for k, v in row.items() if k is not None}


def _load_json(path: Path) -> Iterator[dict[str, Any]]:
    text = _read_text_with_fallback(path)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LoaderError(f"Invalid JSON in {path}: {exc}") from exc

    if isinstance(payload, dict):
        for key in ("reviews", "data", "items", "results"):
            if key in payload and isinstance(payload[key], list):
                payload = payload[key]
                break
        else:
            payload = [payload]

    if not isinstance(payload, list):
        raise LoaderError(f"JSON export must be a list or object wrapper: {path}")

    for item in payload:
        if not isinstance(item, dict):
            continue
        yield item
