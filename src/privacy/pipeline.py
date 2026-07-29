"""Privacy pipeline: load canonical reviews → redact → persist anonymized corpus."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config import PulseConfig, load_config
from src.models import Review
from src.privacy.redactor import RedactionError, RedactionStats, redact_reviews

logger = logging.getLogger(__name__)


@dataclass
class PrivacyResult:
    reviews: list[Review]
    stats: RedactionStats
    blocked: bool = False
    block_reason: str | None = None
    source_path: str | None = None
    output_path: str | None = None
    warnings: list[str] = field(default_factory=list)


def load_canonical_reviews(path: Path) -> list[Review]:
    if not path.is_file():
        raise FileNotFoundError(f"Canonical corpus not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("reviews") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"Invalid canonical format in {path}")
    return [Review.from_dict(row) for row in rows]


def write_anonymized(
    reviews: list[Review],
    stats: RedactionStats,
    path: Path,
    *,
    source_path: str | None = None,
    blocked: bool = False,
    block_reason: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "phase": 2,
        "note": (
            "Anonymized reviews for analysis/compose/delivery. "
            "Do not attach raw exports to Docs/email (P-08)."
        ),
        "source": source_path,
        "blocked": blocked,
        "block_reason": block_reason,
        "redaction": stats.to_dict(),
        "reviews": [r.to_dict() for r in reviews],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote %s anonymized reviews to %s", len(reviews), path)


def anonymize(
    reviews: list[Review] | None = None,
    *,
    config: PulseConfig | None = None,
    canonical_path: Path | None = None,
    output_path: Path | None = None,
    persist: bool = True,
) -> PrivacyResult:
    """
    Phase 2 privacy gate.

    Fail closed (P-06): on redaction error, do not write anonymized corpus
    (or write only an error sidecar) and set blocked=True.
    """
    cfg = config or load_config()
    root = cfg.root
    src = canonical_path or (root / "data" / "processed" / "canonical.json")
    out = output_path or (root / "data" / "processed" / "anonymized.json")

    try:
        if reviews is None:
            reviews = load_canonical_reviews(src)
        redacted, stats = redact_reviews(reviews)
    except (OSError, ValueError, json.JSONDecodeError, RedactionError) as exc:
        reason = f"Privacy gate blocked (fail closed): {exc}"
        logger.error(reason)
        # Do not write unredacted reviews to anonymized.json
        if persist:
            error_path = out.with_suffix(".error.json")
            error_path.parent.mkdir(parents=True, exist_ok=True)
            error_path.write_text(
                json.dumps(
                    {
                        "phase": 2,
                        "blocked": True,
                        "block_reason": reason,
                        "reviews": [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return PrivacyResult(
            reviews=[],
            stats=RedactionStats(),
            blocked=True,
            block_reason=reason,
            source_path=str(src),
            output_path=None,
        )

    if persist:
        write_anonymized(
            redacted,
            stats,
            out,
            source_path=str(src),
            blocked=False,
            block_reason=None,
        )

    return PrivacyResult(
        reviews=redacted,
        stats=stats,
        blocked=False,
        source_path=str(src),
        output_path=str(out) if persist else None,
    )


def format_privacy_report(result: PrivacyResult) -> str:
    s = result.stats
    lines = [
        "=== Privacy metrics ===",
        f"reviews_in:       {s.reviews_in}",
        f"reviews_out:      {s.reviews_out}",
        f"fields_touched:   {s.fields_touched}",
        f"email:            {s.email}",
        f"phone:            {s.phone}",
        f"handle:           {s.handle}",
        f"device_id:        {s.device_id}",
        f"name:             {s.name}",
        f"source:           {result.source_path}",
        f"output:           {result.output_path}",
    ]
    if result.blocked:
        lines.append(f"BLOCKED: {result.block_reason}")
    return "\n".join(lines)
