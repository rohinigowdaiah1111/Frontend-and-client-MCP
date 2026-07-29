"""Review-level categorization for the dashboard.

Splits reviews into "Positive feedback" vs. a per-theme issue bucket (payment
issue, KYC issue, etc.) — this is the classification problemStatement.md/the
dashboard needs per-review, on top of Phase 3's theme_id which only groups
issues, not sentiment.
"""

from __future__ import annotations

from src.models import Review

POSITIVE_RATING_MIN = 4

_ISSUE_LABELS: dict[str, str] = {
    "payments": "Payment issue",
    "kyc": "KYC issue",
    "onboarding": "Onboarding issue",
    "statements": "Statement issue",
    "withdrawals": "Withdrawal issue",
    "other": "Other",
}


def categorize(review: Review) -> tuple[str, str]:
    """Return (category_id, category_label) for one review.

    Positive (rating >= 4) always wins regardless of theme, since a 5-star
    review that happens to mention "KYC" is praise, not an issue report.
    """
    if review.rating is not None and review.rating >= POSITIVE_RATING_MIN:
        return "positive", "Positive feedback"
    theme_id = review.theme_id or "other"
    label = _ISSUE_LABELS.get(theme_id, f"{theme_id.replace('_', ' ').title()} issue")
    return theme_id, label
