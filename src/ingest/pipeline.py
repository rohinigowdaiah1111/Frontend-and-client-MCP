"""Ingest pipeline: load → normalize → window → metrics → optional persist."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from src.config import PulseConfig, load_config
from src.ingest.loader import LoaderError, load_rows
from src.ingest.normalize import (
    NormalizeError,
    content_fingerprint,
    normalize_row,
)
from src.ingest.window import filter_window
from src.models import IngestMetrics, IngestResult, Review, Store

logger = logging.getLogger(__name__)


def _seen_date_bounds(reviews: list[Review]) -> tuple[str | None, str | None]:
    if not reviews:
        return None, None
    dates = [r.date for r in reviews]
    return min(dates).isoformat(), max(dates).isoformat()


def ingest(
    config: PulseConfig | None = None,
    *,
    as_of: date | None = None,
    persist: bool = True,
    output_path: Path | None = None,
) -> IngestResult:
    """
    Run Phase 1 ingest.

    - Public CSV/JSON exports only (no scrape).
    - Partial store OK (I-02); both missing → blocked (I-01).
    - window_weeks validated in config loader (W-03).
    """
    cfg = config or load_config()
    today = as_of or date.today()
    metrics = IngestMetrics()
    normalized: list[Review] = []
    seen_ids: set[str] = set()
    seen_content: set[str] = set()

    enabled_sources = [s for s in cfg.sources if s.enabled]
    if not enabled_sources:
        return IngestResult(
            reviews=[],
            metrics=metrics,
            blocked=True,
            block_reason="No enabled sources in config",
        )

    any_file_loaded = False

    for source in enabled_sources:
        store: Store = source.name  # type: ignore[assignment]
        if not source.path.is_file():
            msg = f"Export missing for {store}: {source.path}"
            logger.warning(msg)
            metrics.warnings.append(msg)
            metrics.stores_missing.append(store)
            continue

        try:
            rows = load_rows(source.path)
        except FileNotFoundError:
            msg = f"Export missing for {store}: {source.path}"
            logger.warning(msg)
            metrics.warnings.append(msg)
            metrics.stores_missing.append(store)
            continue
        except LoaderError as exc:
            msg = f"Cannot read {store} export ({source.path}): {exc}"
            logger.error(msg)
            metrics.errors.append(msg)
            metrics.stores_missing.append(store)
            continue
        except OSError as exc:
            msg = f"Cannot read {store} export ({source.path}): {exc}"
            logger.error(msg)
            metrics.errors.append(msg)
            metrics.stores_missing.append(store)
            continue

        any_file_loaded = True
        metrics.stores_loaded.append(store)
        logger.info("Loaded %s rows from %s (%s)", len(rows), store, source.path.name)

        for row in rows:
            metrics.rows_read += 1
            metrics.by_store_read[store] = metrics.by_store_read.get(store, 0) + 1
            try:
                review = normalize_row(row, store)
            except NormalizeError as exc:
                reason = str(exc)
                if "date" in reason:
                    metrics.dropped_bad_date += 1
                elif "empty text" in reason or "unusable text" in reason:
                    metrics.dropped_empty_text += 1
                else:
                    metrics.dropped_malformed += 1
                logger.debug("Skip %s row: %s", store, exc)
                continue
            except Exception as exc:  # noqa: BLE001 — per-row isolation (I-06)
                metrics.dropped_malformed += 1
                logger.debug("Malformed %s row: %s", store, exc)
                continue

            if review.date > today:
                metrics.dropped_future_date += 1
                continue

            if review.id in seen_ids:
                metrics.dropped_duplicate_id += 1
                continue

            fingerprint = content_fingerprint(review.store, review.text, review.date)
            if fingerprint in seen_content:
                metrics.dropped_duplicate_content += 1
                continue

            seen_ids.add(review.id)
            seen_content.add(fingerprint)
            normalized.append(review)

    if not any_file_loaded:
        reason = "Both store exports missing or unreadable (I-01)"
        metrics.errors.append(reason)
        return IngestResult(reviews=[], metrics=metrics, blocked=True, block_reason=reason)

    metrics.oldest_seen, metrics.newest_seen = _seen_date_bounds(normalized)

    kept, start, end, outside = filter_window(
        normalized,
        as_of=today,
        window_weeks=cfg.window_weeks,
    )
    metrics.window_start = start.isoformat()
    metrics.window_end = end.isoformat()
    metrics.dropped_outside_window = len(outside)
    metrics.kept = len(kept)
    for review in kept:
        metrics.by_store_kept[review.store] = metrics.by_store_kept.get(review.store, 0) + 1

    if not kept:
        warn = (
            f"Empty window {start.isoformat()} -> {end.isoformat()} "
            f"(oldest_seen={metrics.oldest_seen}, newest_seen={metrics.newest_seen})"
        )
        logger.warning(warn)
        metrics.warnings.append(warn)

    result = IngestResult(reviews=kept, metrics=metrics, blocked=False)

    if persist:
        out = output_path or (cfg.root / "data" / "processed" / "canonical.json")
        write_canonical(result, out)

    return result


def write_canonical(result: IngestResult, path: Path) -> None:
    """Persist ingest output for debugging. Prefer redacted corpus after Phase 2."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "phase": 1,
        "note": "Pre-redaction canonical reviews. Phase 2 will write anonymized corpus.",
        "blocked": result.blocked,
        "block_reason": result.block_reason,
        "metrics": result.metrics.to_dict(),
        "reviews": [r.to_dict() for r in result.reviews],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote %s reviews to %s", len(result.reviews), path)


def format_metrics_report(metrics: IngestMetrics) -> str:
    lines = [
        "=== Ingest metrics ===",
        f"rows_read:                {metrics.rows_read}",
        f"dropped_malformed:        {metrics.dropped_malformed}",
        f"dropped_empty_text:       {metrics.dropped_empty_text}",
        f"dropped_bad_date:         {metrics.dropped_bad_date}",
        f"dropped_future_date:      {metrics.dropped_future_date}",
        f"dropped_duplicate_id:     {metrics.dropped_duplicate_id}",
        f"dropped_duplicate_content:{metrics.dropped_duplicate_content}",
        f"dropped_outside_window:   {metrics.dropped_outside_window}",
        f"kept:                     {metrics.kept}",
        f"by_store_read:            {metrics.by_store_read}",
        f"by_store_kept:            {metrics.by_store_kept}",
        f"window:                   {metrics.window_start} -> {metrics.window_end}",
        f"oldest_seen:              {metrics.oldest_seen}",
        f"newest_seen:              {metrics.newest_seen}",
        f"stores_loaded:            {metrics.stores_loaded}",
        f"stores_missing:           {metrics.stores_missing}",
    ]
    if metrics.warnings:
        lines.append("warnings:")
        lines.extend(f"  - {w}" for w in metrics.warnings)
    if metrics.errors:
        lines.append("errors:")
        lines.extend(f"  - {e}" for e in metrics.errors)
    return "\n".join(lines)
