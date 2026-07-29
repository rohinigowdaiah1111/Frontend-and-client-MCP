"""Keyword/rules-based theme classification (architecture §6: 'keep simple first')."""

from __future__ import annotations

# Curated synonyms for the default product theme vocabulary. Custom labels not
# listed here fall back to matching the label word itself (see classify_review).
THEME_SYNONYMS: dict[str, list[str]] = {
    "onboarding": [
        "onboarding", "onboard", "sign up", "signup", "sign-up",
        "welcome screen", "tutorial", "first-time", "first time",
        "permission", "get started", "setup", "set up", "registration",
    ],
    "kyc": [
        "kyc", "know your customer", "verify identity", "identity verification",
        "document upload", "id upload", "selfie", "rejected", "pending verification",
        "verification failed", "upload id",
    ],
    "payments": [
        "payment", "pay ", "charge", "checkout", "declined", "decline",
        "otp", "transaction failed", "card", "upi", "billing", "charged twice",
    ],
    "statements": [
        "statement", "pdf", "csv", "export", "balance", "transaction history",
        "ledger", "opening balance", "closing balance",
    ],
    "withdrawals": [
        "withdraw", "withdrawal", "payout", "cash out", "bank transfer",
        "eta", "pending withdrawal", "withdrawal limit",
    ],
}

OTHER_THEME_ID = "other"


def _count_hits(text_lower: str, synonyms: list[str]) -> int:
    return sum(text_lower.count(term) for term in synonyms)


def classify_review(text: str, labels: list[str]) -> str:
    """
    Assign a review to the best-matching configured theme label, or 'other'.

    Deterministic: ties broken by earliest label in config order (T-07 style).
    """
    text_lower = (text or "").lower()
    best_label = None
    best_hits = 0

    for label in labels:
        key = label.strip().lower()
        synonyms = THEME_SYNONYMS.get(key, [key.replace("_", " ").replace("-", " ")])
        hits = _count_hits(text_lower, synonyms)
        if hits > best_hits:
            best_hits = hits
            best_label = label

    return best_label if best_label else OTHER_THEME_ID
