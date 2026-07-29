"""Builds the live dashboard payload straight from data/raw (problemStatement.md).

Runs Phase 1 (ingest) -> Phase 2 (privacy) -> Phase 3 (theme clustering) in
memory, the same functions the CLI pipeline uses, then adds a per-review
category (webapp/categorize.py) for the dashboard's chart + filterable list.
This is the real replacement for the earlier static Stitch mockup's sample data.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.analysis.pipeline import analyze
from src.config import PulseConfig, load_config
from src.ingest.pipeline import ingest
from src.privacy.pipeline import anonymize
from webapp.categorize import categorize

_EMPTY: dict[str, Any] = {
    "blocked": False,
    "block_reason": None,
    "week_of": None,
    "window_start": None,
    "window_end": None,
    "total_reviews": 0,
    "by_store": {},
    "categories": [],
    "themes_top": [],
    "themes_all": [],
    "quotes": [],
    "actions": [],
    "limitation_note": None,
    "reviews": [],
}


def build_dashboard(config: PulseConfig | None = None, *, as_of: date | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    today = as_of or date.today()

    ingest_result = ingest(cfg, as_of=today, persist=True)
    if ingest_result.blocked:
        return {**_EMPTY, "blocked": True, "block_reason": ingest_result.block_reason}

    privacy_result = anonymize(ingest_result.reviews, config=cfg, persist=True)
    if privacy_result.blocked:
        return {**_EMPTY, "blocked": True, "block_reason": privacy_result.block_reason}

    reviews = privacy_result.reviews
    payload = analyze(reviews, config=cfg, as_of=today, persist=True)

    categories: dict[str, dict[str, Any]] = {}
    review_rows: list[dict[str, Any]] = []
    for r in reviews:
        cat_id, cat_label = categorize(r)
        bucket = categories.setdefault(cat_id, {"id": cat_id, "label": cat_label, "count": 0})
        bucket["count"] += 1
        review_rows.append(
            {
                "id": r.id,
                "store": r.store,
                "rating": r.rating,
                "title": r.title,
                "text": r.text,
                "date": r.date.isoformat(),
                "theme_id": r.theme_id,
                "category_id": cat_id,
                "category_label": cat_label,
            }
        )

    review_rows.sort(key=lambda row: row["date"], reverse=True)

    return {
        "blocked": False,
        "block_reason": None,
        "week_of": payload.week_of,
        "window_start": payload.window_start,
        "window_end": payload.window_end,
        "total_reviews": payload.total_reviews,
        "by_store": payload.by_store,
        "categories": sorted(categories.values(), key=lambda c: c["count"], reverse=True),
        "themes_top": [t.to_dict() for t in payload.themes_top],
        "themes_all": [t.to_dict() for t in payload.themes_all],
        "quotes": [q.to_dict() for q in payload.quotes],
        "actions": [a.to_dict() for a in payload.actions],
        "limitation_note": payload.limitation_note,
        "reviews": review_rows,
    }
