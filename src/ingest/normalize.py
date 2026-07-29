"""Schema normalizer: store-specific rows → canonical Review."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any

from src.models import Review, Store

TEXT_ALIASES = ("text", "review", "body", "content", "review_text", "comment")
TITLE_ALIASES = ("title", "headline", "review_title")
DATE_ALIASES = ("date", "created_date", "review_date", "created_at", "updated", "time")
RATING_ALIASES = ("rating", "star", "stars", "score")
ID_ALIASES = ("review_id", "id", "reviewid", "review_uuid")

# Drop identity columns — never copy into canonical model (P-05 / EXPORT_SCHEMA).
IDENTITY_FIELDS = {
    "username",
    "author",
    "email",
    "device_id",
    "reviewer_name",
    "reviewer",
    "user",
    "user_name",
    "name",
}

RATING_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}

_HTML_TAG = re.compile(r"<[^>]+>")


class NormalizeError(ValueError):
    """Row cannot be normalized."""


def _pick(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    lower_map = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in aliases:
        if alias in lower_map and lower_map[alias] not in (None, ""):
            return lower_map[alias]
    return None


def _strip_html(value: str) -> str:
    return _HTML_TAG.sub(" ", value).strip()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _strip_html(str(value)).strip()
    return text or None


def parse_rating(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        rating = int(value)
        return rating if 1 <= rating <= 5 else None

    raw = str(value).strip().lower()
    raw = raw.replace("stars", "").replace("star", "").strip()
    if raw in RATING_WORDS:
        return RATING_WORDS[raw]
    try:
        rating = int(float(raw))
    except ValueError:
        return None
    return rating if 1 <= rating <= 5 else None


def parse_date(value: Any) -> date:
    if value is None or value == "":
        raise NormalizeError("missing date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    if "T" in raw or raw.endswith("Z"):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise NormalizeError(f"unparseable date: {value!r}") from exc

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError as exc:
        raise NormalizeError(f"unparseable date: {value!r}") from exc


def stable_id(store: Store, export_key: str) -> str:
    digest = hashlib.sha256(f"{store}:{export_key}".encode("utf-8")).hexdigest()
    return digest[:16]


def content_fingerprint(store: Store, text: str, review_date: date) -> str:
    normalized = " ".join(text.lower().split())
    digest = hashlib.sha256(f"{store}:{review_date.isoformat()}:{normalized}".encode("utf-8")).hexdigest()
    return digest[:16]


def usable_text(text: str) -> bool:
    """Skip emoji-only / gibberish with no alphanumeric content (N-08)."""
    alnum = sum(1 for ch in text if ch.isalnum())
    return alnum >= 3


def normalize_row(row: dict[str, Any], store: Store) -> Review:
    # Never promote identity fields into the model.
    safe_row = {k: v for k, v in row.items() if str(k).strip().lower() not in IDENTITY_FIELDS}

    export_key_raw = _pick(safe_row, ID_ALIASES)
    if export_key_raw is None:
        # Fall back to hash of available fields so duplicates can still be detected.
        export_key = hashlib.sha256(repr(sorted(safe_row.items())).encode("utf-8")).hexdigest()[:12]
    else:
        export_key = str(export_key_raw).strip()

    title = _clean_text(_pick(safe_row, TITLE_ALIASES))
    text = _clean_text(_pick(safe_row, TEXT_ALIASES))
    if not text and title:
        text = title  # N-01
        title = title if title != text else title
    if not text:
        raise NormalizeError("empty text")
    if not usable_text(text):
        raise NormalizeError("unusable text")

    review_date = parse_date(_pick(safe_row, DATE_ALIASES))
    rating = parse_rating(_pick(safe_row, RATING_ALIASES))

    return Review(
        id=stable_id(store, export_key),
        store=store,
        rating=rating,
        title=title,
        text=text,
        date=review_date,
        export_key=export_key,
    )
