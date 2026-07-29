"""Shared data models for the weekly review pulse pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Literal

Store = Literal["app_store", "play_store"]


@dataclass
class Review:
    """Canonical review (architecture §5). After Phase 2, title/text are redacted."""

    id: str
    store: Store
    rating: int | None
    title: str | None
    text: str
    date: date
    theme_id: str | None = None
    export_key: str | None = None  # original review_id for debugging; not PII

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["date"] = self.date.isoformat()
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Review:
        raw_date = data["date"]
        parsed = date.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
        return cls(
            id=data["id"],
            store=data["store"],
            rating=data.get("rating"),
            title=data.get("title"),
            text=data["text"],
            date=parsed,
            theme_id=data.get("theme_id"),
            export_key=data.get("export_key"),
        )


@dataclass
class IngestMetrics:
    rows_read: int = 0
    dropped_malformed: int = 0
    dropped_empty_text: int = 0
    dropped_bad_date: int = 0
    dropped_future_date: int = 0
    dropped_outside_window: int = 0
    dropped_duplicate_id: int = 0
    dropped_duplicate_content: int = 0
    kept: int = 0
    by_store_read: dict[str, int] = field(default_factory=lambda: {"app_store": 0, "play_store": 0})
    by_store_kept: dict[str, int] = field(default_factory=lambda: {"app_store": 0, "play_store": 0})
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    window_start: str | None = None
    window_end: str | None = None
    oldest_seen: str | None = None
    newest_seen: str | None = None
    stores_loaded: list[str] = field(default_factory=list)
    stores_missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IngestResult:
    reviews: list[Review]
    metrics: IngestMetrics
    blocked: bool = False
    block_reason: str | None = None


@dataclass
class FinalEmail:
    subject: str
    body: str

    def to_dict(self) -> dict[str, Any]:
        return {"subject": self.subject, "body": self.body}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FinalEmail:
        return cls(subject=str(data.get("subject") or ""), body=str(data.get("body") or ""))


@dataclass
class GroqFinalCopy:
    """Stakeholder-facing copy produced by Groq (Phase 4b)."""

    report_markdown: str
    email: FinalEmail
    model: str
    word_count: int
    retries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_markdown": self.report_markdown,
            "email": self.email.to_dict(),
            "model": self.model,
            "word_count": self.word_count,
            "retries": self.retries,
        }


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeliveryGateResult:
    allowed: bool
    reason: str | None = None
    report_path: str | None = None
    email_path: str | None = None
    report_body: str | None = None
    email: FinalEmail | None = None


@dataclass
class ThemeMetrics:
    count: int
    avg_rating: float | None
    recent_share: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Theme:
    """Theme cluster (architecture §5). id/label share the config theme label or 'other'."""

    id: str
    label: str
    review_ids: list[str]
    metrics: ThemeMetrics
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "review_ids": self.review_ids,
            "metrics": self.metrics.to_dict(),
            "score": self.score,
        }


@dataclass
class QuoteItem:
    text: str
    theme_id: str
    store: Store
    rating: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionItem:
    text: str
    theme_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PulsePayload:
    """Structured, pre-composition pulse facts (architecture §5)."""

    week_of: str
    window_start: str
    window_end: str
    themes_all: list[Theme]
    themes_top: list[Theme]
    quotes: list[QuoteItem]
    actions: list[ActionItem]
    total_reviews: int
    by_store: dict[str, int]
    limitation_note: str | None = None

    def to_fact_pack(self) -> dict[str, Any]:
        """Shape consumed by src/compose (Phase 4b Groq writer)."""
        return {
            "week_of": self.week_of,
            "window": {"start": self.window_start, "end": self.window_end},
            "stats": {"total_reviews": self.total_reviews, "by_store": self.by_store},
            "themes_all": [t.to_dict() for t in self.themes_all],
            "themes_top": [t.to_dict() for t in self.themes_top],
            "quotes": [q.to_dict() for q in self.quotes],
            "actions": [a.to_dict() for a in self.actions],
            "limitation_note": self.limitation_note,
        }
