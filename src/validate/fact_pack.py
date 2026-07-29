"""Phase 4 — Pre-LLM Constraint Validator for a Phase 3 fact pack.

Runs before Groq (Phase 4b) is ever called. Hard errors block progression;
sparse-data shortfalls are warnings when config.pulse.allow_sparse is true.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import PulseConfig
from src.models import ValidationReport
from src.validate.checks import find_pii


def _load_corpus_texts(anonymized_path: Path) -> set[str] | None:
    """Load redacted review text/title for the verbatim cross-check. None if unavailable."""
    if not anonymized_path.is_file():
        return None
    try:
        data = json.loads(anonymized_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    texts: set[str] = set()
    for row in data.get("reviews", []):
        if not isinstance(row, dict):
            continue
        text = row.get("text")
        if text:
            texts.add(str(text))
        title = row.get("title")
        if title:
            texts.add(str(title))
    return texts


def validate_fact_pack(
    fact_pack: dict[str, Any],
    *,
    config: PulseConfig,
    anonymized_path: Path | None = None,
) -> ValidationReport:
    """
    Validate a Phase 3 fact pack before it is handed to Groq.

    Hard checks (block Phase 4b): theme/quote/action counts over config limits,
    PII in any text field, quotes not verbatim in the anonymized corpus (when
    available), actions not grounded in a known theme, stats inconsistency (V-03).

    Soft checks (warn only, when allow_sparse): fewer quotes/actions/themes than
    the configured target — legitimate for empty/sparse review windows (T-03/T-04).
    """
    errors: list[str] = []
    warnings: list[str] = []

    themes_all = fact_pack.get("themes_all") or []
    themes_top = fact_pack.get("themes_top") or []
    quotes = fact_pack.get("quotes") or []
    actions = fact_pack.get("actions") or []
    stats = fact_pack.get("stats") or {}

    if len(themes_all) > config.theme_max:
        errors.append(
            f"themes_all has {len(themes_all)} themes, exceeding themes.max={config.theme_max} (T-05 analog)"
        )
    if len(themes_top) > config.pulse.top_themes:
        errors.append(
            f"themes_top has {len(themes_top)} themes, exceeding pulse.top_themes={config.pulse.top_themes}"
        )

    theme_ids_all = {t.get("id") for t in themes_all if isinstance(t, dict)}

    # --- Quotes ---
    if len(quotes) > config.pulse.quotes:
        errors.append(
            f"quotes has {len(quotes)} entries, exceeding pulse.quotes={config.pulse.quotes}"
        )
    elif len(quotes) < config.pulse.quotes:
        msg = f"Only {len(quotes)} of {config.pulse.quotes} quotes available"
        (warnings if config.pulse.allow_sparse else errors).append(msg)

    corpus_texts = _load_corpus_texts(
        anonymized_path or (config.root / "data" / "processed" / "anonymized.json")
    )
    if corpus_texts is None:
        warnings.append("Anonymized corpus not found — skipped verbatim cross-check (Q-06 defense)")

    for q in quotes:
        if not isinstance(q, dict):
            errors.append(f"Malformed quote entry: {q!r}")
            continue
        text = str(q.get("text") or "")
        if not text.strip():
            errors.append("Empty quote text")
            continue
        pii = find_pii(text)
        if pii:
            errors.append(f"PII detected in quote: {', '.join(pii)}")
        theme_id = q.get("theme_id")
        if theme_id and theme_ids_all and theme_id not in theme_ids_all:
            errors.append(f"Quote references unknown theme_id={theme_id!r}")
        if corpus_texts is not None and text not in corpus_texts:
            errors.append(f"Quote is not verbatim in anonymized corpus (Q-06/G-03): {text[:80]!r}")

    # --- Actions ---
    if len(actions) > config.pulse.actions:
        errors.append(
            f"actions has {len(actions)} entries, exceeding pulse.actions={config.pulse.actions}"
        )
    elif len(actions) < config.pulse.actions:
        msg = f"Only {len(actions)} of {config.pulse.actions} actions available"
        (warnings if config.pulse.allow_sparse else errors).append(msg)

    for a in actions:
        if not isinstance(a, dict):
            errors.append(f"Malformed action entry: {a!r}")
            continue
        text = str(a.get("text") or "")
        theme_ids = a.get("theme_ids") or []
        if not text.strip():
            errors.append("Empty action text")
        if not theme_ids:
            errors.append(f"Action not grounded in any theme (A-03): {text[:60]!r}")
        elif theme_ids_all and any(tid not in theme_ids_all for tid in theme_ids):
            errors.append(f"Action references unknown theme_ids={theme_ids!r}")
        if find_pii(text):
            errors.append(f"PII detected in action text: {text[:60]!r}")

    # --- Stats consistency (V-03) ---
    by_store = stats.get("by_store") or {}
    total = stats.get("total_reviews")
    if isinstance(total, int) and isinstance(by_store, dict):
        store_sum = sum(v for v in by_store.values() if isinstance(v, int))
        if store_sum != total:
            errors.append(
                f"stats.total_reviews={total} does not match sum(by_store)={store_sum} (V-03)"
            )

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings)
