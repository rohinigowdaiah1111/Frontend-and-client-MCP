"""Quote Selector — verbatim, anonymous, one-per-top-theme when possible (§6 rules)."""

from __future__ import annotations

from src.models import QuoteItem, Review, Theme
from src.privacy.redactor import find_pii_kinds

MIN_QUOTE_WORDS = 4  # Q-02: skip one-word praise/complaints like "Good" / "Bad"


def _is_usable(review: Review) -> bool:
    text = (review.text or "").strip()
    if not text or text == "[redacted]":
        return False
    if len(text.split()) < MIN_QUOTE_WORDS:
        return False
    hard_pii = [k for k in find_pii_kinds(text) if k != "name"]
    if hard_pii:  # Q-03: residual PII disqualifies a candidate
        return False
    return True


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _concreteness_key(review: Review):
    # Prefer reviews with specific detail (digits, dates, versions) then longer text (Q-02).
    has_digit = any(ch.isdigit() for ch in review.text)
    return (-int(has_digit), -len(review.text))


def select_quotes(
    themes_top: list[Theme],
    reviews: list[Review],
    *,
    target: int,
) -> list[QuoteItem]:
    """
    Pick up to `target` verbatim quotes, preferring one per top theme (Q-04/Q-08).
    Never invents text; returns fewer than target if not enough usable reviews (Q-01).
    Deduplicates near-identical quotes (Q-07).
    """
    if target <= 0 or not themes_top:
        return []

    reviews_by_id = {r.id: r for r in reviews}
    used_ids: set[str] = set()
    used_norm: set[str] = set()
    quotes: list[QuoteItem] = []

    def candidates_for(theme: Theme) -> list[Review]:
        cands = [reviews_by_id[rid] for rid in theme.review_ids if rid in reviews_by_id]
        cands = [
            r
            for r in cands
            if _is_usable(r) and r.id not in used_ids and _normalize(r.text) not in used_norm
        ]
        cands.sort(key=_concreteness_key)
        return cands

    def take(theme: Theme) -> bool:
        cands = candidates_for(theme)
        if not cands:
            return False
        chosen = cands[0]
        quotes.append(
            QuoteItem(text=chosen.text, theme_id=theme.id, store=chosen.store, rating=chosen.rating)
        )
        used_ids.add(chosen.id)
        used_norm.add(_normalize(chosen.text))
        return True

    # Pass 1: one quote per top theme, in rank order
    for theme in themes_top:
        if len(quotes) >= target:
            break
        take(theme)

    # Pass 2: fill remaining slots from any top theme with leftover candidates
    guard = 0
    while len(quotes) < target and guard < target * len(themes_top) + 5:
        guard += 1
        added = False
        for theme in themes_top:
            if len(quotes) >= target:
                break
            if take(theme):
                added = True
        if not added:
            break  # Q-01: exhausted usable candidates; do not invent

    return quotes
