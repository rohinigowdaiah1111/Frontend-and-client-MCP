"""Theme Clusterer — assign reviews to at most `theme_max` themes (T-01)."""

from __future__ import annotations

from datetime import date, timedelta

from src.analysis.keywords import OTHER_THEME_ID, classify_review
from src.models import Review, Theme, ThemeMetrics

RECENT_WINDOW_DAYS = 14


def assign_themes(reviews: list[Review], labels: list[str]) -> list[Review]:
    """Mutate reviews in place, setting theme_id from keyword classification."""
    for review in reviews:
        combined = f"{review.title or ''} {review.text}"
        review.theme_id = classify_review(combined, labels)
    return reviews


def _make_theme(theme_id: str, revs: list[Review], *, window_end: date) -> Theme:
    ratings = [r.rating for r in revs if r.rating is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
    cutoff = window_end - timedelta(days=RECENT_WINDOW_DAYS)
    recent = sum(1 for r in revs if r.date >= cutoff)
    recent_share = round(recent / len(revs), 3) if revs else 0.0
    return Theme(
        id=theme_id,
        label=theme_id,
        review_ids=[r.id for r in revs],
        metrics=ThemeMetrics(count=len(revs), avg_rating=avg_rating, recent_share=recent_share),
    )


def build_themes(
    reviews: list[Review],
    *,
    window_end: date,
    theme_max: int,
) -> list[Theme]:
    """
    Group already-classified reviews into Theme objects, capped at theme_max (T-01).
    Overflow is merged into 'other' by repeatedly folding the smallest named theme in.
    Empty input yields an empty list (T-04).
    """
    groups: dict[str, list[Review]] = {}
    for review in reviews:
        groups.setdefault(review.theme_id or OTHER_THEME_ID, []).append(review)

    themes: dict[str, Theme] = {
        tid: _make_theme(tid, revs, window_end=window_end) for tid, revs in groups.items()
    }

    reviews_by_id = {r.id: r for r in reviews}
    while len(themes) > theme_max:
        named = [t for tid, t in themes.items() if tid != OTHER_THEME_ID]
        if not named:
            break  # only "other" remains; nothing left to merge
        smallest = min(named, key=lambda t: (t.metrics.count, t.id))
        del themes[smallest.id]

        existing_other = themes.get(OTHER_THEME_ID)
        merged_ids = (existing_other.review_ids if existing_other else []) + smallest.review_ids
        merged_revs = [reviews_by_id[rid] for rid in merged_ids if rid in reviews_by_id]
        themes[OTHER_THEME_ID] = _make_theme(OTHER_THEME_ID, merged_revs, window_end=window_end)

    return list(themes.values())
