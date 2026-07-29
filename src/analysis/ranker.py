"""Theme Ranker — score by volume × severity × recency, select top N (T-07, T-08)."""

from __future__ import annotations

from src.analysis.keywords import OTHER_THEME_ID
from src.models import Review, Theme

W_VOLUME = 0.50
W_SEVERITY = 0.35
W_RECENCY = 0.15

LOW_RATING_MAX = 2  # ratings <= this count as "low" for severity


def _low_rating_share(revs: list[Review]) -> float:
    rated = [r for r in revs if r.rating is not None]
    if not rated:
        return 0.0
    low = sum(1 for r in rated if r.rating <= LOW_RATING_MAX)
    return low / len(rated)


def score_themes(themes: list[Theme], reviews: list[Review]) -> list[Theme]:
    """Assign a normalized score to each theme in place. Returns the same list."""
    if not themes:
        return themes

    reviews_by_id = {r.id: r for r in reviews}
    revs_by_theme: dict[str, list[Review]] = {
        t.id: [reviews_by_id[rid] for rid in t.review_ids if rid in reviews_by_id] for t in themes
    }
    low_shares = {tid: _low_rating_share(revs) for tid, revs in revs_by_theme.items()}

    max_count = max((t.metrics.count for t in themes), default=0) or 1
    max_recent = max((t.metrics.recent_share for t in themes), default=0.0) or 1e-9
    max_low = max(low_shares.values(), default=0.0) or 1e-9

    for t in themes:
        v = t.metrics.count / max_count
        s = low_shares[t.id] / max_low
        r = t.metrics.recent_share / max_recent
        t.score = round(W_VOLUME * v + W_SEVERITY * s + W_RECENCY * r, 4)

    return themes


def _sort_key(t: Theme):
    # T-07: higher score -> higher count -> lower avg rating (more urgent) -> alphabetical id
    avg = t.metrics.avg_rating if t.metrics.avg_rating is not None else 99.0
    return (-t.score, -t.metrics.count, avg, t.id)


def rank_top_themes(themes: list[Theme], *, top_n: int) -> list[Theme]:
    """
    Select up to top_n themes, deterministically ordered.
    Demotes 'other' when a more specific theme is available just outside top_n (T-08).
    """
    if not themes or top_n <= 0:
        return []

    ranked = sorted(themes, key=_sort_key)
    top = ranked[:top_n]

    if any(t.id == OTHER_THEME_ID for t in top) and len(ranked) > top_n:
        specific_below = [t for t in ranked[top_n:] if t.id != OTHER_THEME_ID]
        if specific_below:
            top = [t for t in top if t.id != OTHER_THEME_ID]
            top.append(specific_below[0])
            top = sorted(top, key=_sort_key)

    return top[:top_n]
