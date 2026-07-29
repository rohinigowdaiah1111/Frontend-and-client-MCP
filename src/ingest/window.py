"""Date window filter (8–12 weeks, inclusive calendar bounds)."""

from __future__ import annotations

from datetime import date, timedelta

from src.models import Review


def window_bounds(as_of: date, window_weeks: int) -> tuple[date, date]:
    """Inclusive [start, end] where end is as_of and start is as_of - window_weeks weeks."""
    start = as_of - timedelta(weeks=window_weeks)
    return start, as_of


def in_window(review_date: date, start: date, end: date) -> bool:
    return start <= review_date <= end


def filter_window(
    reviews: list[Review],
    *,
    as_of: date,
    window_weeks: int,
) -> tuple[list[Review], date, date, list[Review]]:
    """Returns (kept, start, end, outside)."""
    start, end = window_bounds(as_of, window_weeks)
    kept: list[Review] = []
    outside: list[Review] = []
    for review in reviews:
        if in_window(review.date, start, end):
            kept.append(review)
        else:
            outside.append(review)
    return kept, start, end, outside
