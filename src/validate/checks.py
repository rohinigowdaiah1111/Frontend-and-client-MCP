"""Shared validation helpers (PII + word count + verbatim quotes)."""

from __future__ import annotations

from typing import Iterable

from src.models import ValidationReport
from src.privacy.redactor import find_pii_kinds


def word_count(text: str) -> int:
    return len(text.split())


def find_pii(text: str) -> list[str]:
    """Detect residual hard PII kinds (aligned with privacy redactor)."""
    return [k for k in find_pii_kinds(text) if k != "name"]


def quotes_are_verbatim(body: str, quotes: Iterable[str]) -> list[str]:
    """Return quotes that are missing from body (invented/rewritten)."""
    missing: list[str] = []
    for quote in quotes:
        q = quote.strip()
        if not q:
            continue
        if q not in body:
            missing.append(q)
    return missing


def validate_final_copy(
    *,
    report: str,
    email_body: str,
    quotes: list[str],
    max_words: int,
    allow_sparse: bool = True,
) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if not report.strip():
        errors.append("Empty Groq report")
    if not email_body.strip():
        errors.append("Empty Groq email body")

    wc = word_count(report)
    if wc > max_words:
        errors.append(f"Report word count {wc} exceeds max_words={max_words}")

    for label, text in (("report", report), ("email", email_body)):
        pii = find_pii(text)
        if pii:
            errors.append(f"PII detected in {label}: {', '.join(pii)}")

    if quotes:
        missing_in_report = quotes_are_verbatim(report, quotes)
        if missing_in_report:
            errors.append(
                "Groq output missing verbatim quotes (possible rewrite): "
                + "; ".join(m[:80] for m in missing_in_report[:3])
            )
    elif allow_sparse:
        warnings.append("No quotes to verify (sparse/empty window)")

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)
