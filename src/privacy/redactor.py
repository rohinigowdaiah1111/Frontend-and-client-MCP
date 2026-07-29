"""PII Redactor — scrub identity from review title/text (fail closed)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from src.models import Review
from src.privacy.patterns import (
    DEFAULT_STRIP_FIELDS,
    EMAIL_RE,
    FIRST_PERSON_NAME_RE,
    HANDLE_RE,
    HEX_TOKEN_RE,
    IMEI_RE,
    PHONE_RE,
    PLACEHOLDERS,
    UUID_RE,
)


class RedactionError(RuntimeError):
    """Redaction could not complete safely (P-06 fail closed)."""


@dataclass
class RedactionStats:
    reviews_in: int = 0
    reviews_out: int = 0
    fields_touched: int = 0
    email: int = 0
    phone: int = 0
    handle: int = 0
    device_id: int = 0
    name: int = 0

    def to_dict(self) -> dict:
        return {
            "reviews_in": self.reviews_in,
            "reviews_out": self.reviews_out,
            "fields_touched": self.fields_touched,
            "replacements": {
                "email": self.email,
                "phone": self.phone,
                "handle": self.handle,
                "device_id": self.device_id,
                "name": self.name,
            },
        }


def find_pii_kinds(text: str) -> list[str]:
    """Return PII kind labels present in text."""
    if not text:
        return []
    hits: list[str] = []
    if EMAIL_RE.search(text):
        hits.append("email")
    if PHONE_RE.search(text):
        hits.append("phone")
    if HANDLE_RE.search(text):
        hits.append("handle")
    if UUID_RE.search(text) or IMEI_RE.search(text) or HEX_TOKEN_RE.search(text):
        hits.append("device_or_uuid")
    if FIRST_PERSON_NAME_RE.search(text):
        hits.append("name")
    return hits


def redact_text(text: str | None, stats: RedactionStats | None = None) -> str:
    """Replace PII tokens with placeholders."""
    if text is None:
        return ""
    original = text
    out = text

    def _bump(attr: str) -> None:
        if stats is not None:
            setattr(stats, attr, getattr(stats, attr) + 1)

    def _repl(attr: str, key: str):
        def _inner(_match: re.Match[str]) -> str:
            _bump(attr)
            return PLACEHOLDERS[key]

        return _inner

    out = EMAIL_RE.sub(_repl("email", "email"), out)
    out = HANDLE_RE.sub(_repl("handle", "handle"), out)
    # Device tokens before phone — phone patterns can false-match digit runs inside UUIDs
    out = UUID_RE.sub(_repl("device_id", "uuid"), out)
    out = IMEI_RE.sub(_repl("device_id", "imei"), out)
    out = HEX_TOKEN_RE.sub(_repl("device_id", "hex_token"), out)
    out = PHONE_RE.sub(_repl("phone", "phone"), out)

    def _name_repl(match: re.Match[str]) -> str:
        _bump("name")
        return f"{match.group(1)}{PLACEHOLDERS['name']}"

    out = FIRST_PERSON_NAME_RE.sub(_name_repl, out)

    if stats is not None and out != original:
        stats.fields_touched += 1
    return out


def drop_strip_fields(row: dict, strip_fields: Iterable[str] | None = None) -> dict:
    """Remove identity columns from a raw mapping (P-05)."""
    banned = {f.lower() for f in (strip_fields or DEFAULT_STRIP_FIELDS)}
    return {k: v for k, v in row.items() if str(k).strip().lower() not in banned}


def redact_review(
    review: Review,
    *,
    stats: RedactionStats | None = None,
    fail_closed_residual: bool = True,
) -> Review:
    """Return a new Review with title/text scrubbed."""
    try:
        title_raw = redact_text(review.title, stats) if review.title else None
        title = title_raw.strip() if title_raw and title_raw.strip() else None
        text = redact_text(review.text, stats)
        if not text.strip():
            text = "[redacted]"

        redacted = Review(
            id=review.id,
            store=review.store,
            rating=review.rating,
            title=title,
            text=text,
            date=review.date,
            theme_id=review.theme_id,
            export_key=review.export_key,
        )
        residual = find_pii_kinds((redacted.title or "") + "\n" + redacted.text)
        hard = [k for k in residual if k != "name"]
        if hard and fail_closed_residual:
            raise RedactionError(
                f"Residual PII after redaction on review {review.id}: {', '.join(hard)}"
            )
        return redacted
    except RedactionError:
        raise
    except Exception as exc:  # noqa: BLE001 — fail closed (P-06)
        raise RedactionError(f"Redactor failed on review {review.id}: {exc}") from exc


def redact_reviews(reviews: list[Review]) -> tuple[list[Review], RedactionStats]:
    """Redact all reviews. On any failure, raise — do not return partial corpus."""
    stats = RedactionStats(reviews_in=len(reviews))
    out: list[Review] = []
    try:
        for review in reviews:
            out.append(redact_review(review, stats=stats, fail_closed_residual=True))
        stats.reviews_out = len(out)
        return out, stats
    except Exception as exc:
        raise RedactionError(str(exc)) from exc
