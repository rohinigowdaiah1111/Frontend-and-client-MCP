"""Phase 3 analysis pipeline: cluster -> rank -> quotes -> actions -> PulsePayload."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from src.analysis.actions import generate_actions
from src.analysis.clusterer import assign_themes, build_themes
from src.analysis.quotes import select_quotes
from src.analysis.ranker import rank_top_themes, score_themes
from src.compose.facts import write_fact_pack
from src.config import PulseConfig, load_config
from src.models import PulsePayload, Review

logger = logging.getLogger(__name__)


class AnalysisBlocked(RuntimeError):
    """Analysis cannot proceed (e.g. upstream privacy gate blocked)."""


def load_anonymized_reviews(path: Path) -> list[Review]:
    if not path.is_file():
        raise FileNotFoundError(f"Anonymized corpus not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("blocked"):
        raise AnalysisBlocked(
            f"Cannot analyze: privacy gate blocked ({payload.get('block_reason')})"
        )
    rows = payload.get("reviews", [])
    return [Review.from_dict(row) for row in rows]


def analyze(
    reviews: list[Review] | None = None,
    *,
    config: PulseConfig | None = None,
    anonymized_path: Path | None = None,
    as_of: date | None = None,
    persist: bool = True,
    output_path: Path | None = None,
) -> PulsePayload:
    """
    Phase 3: theme clustering, ranking, quote selection, action ideation.

    Input reviews must already be anonymized (Phase 2). Writes output/pulse-facts.json
    for Phase 4b (Groq) to consume.
    """
    cfg = config or load_config()
    root = cfg.root
    today = as_of or date.today()

    if reviews is None:
        src_path = anonymized_path or (root / "data" / "processed" / "anonymized.json")
        reviews = load_anonymized_reviews(src_path)

    window_start = today - timedelta(weeks=cfg.window_weeks)
    labels = cfg.theme_labels

    assign_themes(reviews, labels)
    themes_all = build_themes(reviews, window_end=today, theme_max=cfg.theme_max)
    themes_all = score_themes(themes_all, reviews)
    themes_top = rank_top_themes(themes_all, top_n=cfg.pulse.top_themes)

    quotes = select_quotes(themes_top, reviews, target=cfg.pulse.quotes)
    actions = generate_actions(themes_top, target=cfg.pulse.actions)

    by_store: dict[str, int] = {"app_store": 0, "play_store": 0}
    for r in reviews:
        by_store[r.store] = by_store.get(r.store, 0) + 1

    limitation_note = _build_limitation_note(
        reviews=reviews,
        themes_top=themes_top,
        quotes=quotes,
        actions=actions,
        cfg=cfg,
    )

    payload = PulsePayload(
        week_of=today.isoformat(),
        window_start=window_start.isoformat(),
        window_end=today.isoformat(),
        themes_all=themes_all,
        themes_top=themes_top,
        quotes=quotes,
        actions=actions,
        total_reviews=len(reviews),
        by_store=by_store,
        limitation_note=limitation_note,
    )

    if persist:
        out = output_path or (root / "output" / "pulse-facts.json")
        write_fact_pack(payload.to_fact_pack(), out)
        logger.info("Wrote fact pack to %s", out)

    return payload


def _build_limitation_note(
    *,
    reviews: list[Review],
    themes_top,
    quotes,
    actions,
    cfg: PulseConfig,
) -> str | None:
    if not reviews:
        return "No reviews in this window — no themes invented."  # W-01 style
    if not themes_top:
        return "No assignable themes found this week — no signal invented."  # T-04
    if len(quotes) < cfg.pulse.quotes:
        return f"Limited sample — only {len(quotes)} usable quote(s) found (no invented wording)."
    if len(actions) < cfg.pulse.actions:
        return f"Limited sample — only {len(actions)} grounded action(s) available."
    if len(themes_top) < cfg.pulse.top_themes:
        return "Limited theme diversity this week — fewer than the usual top themes."
    return None


def format_analysis_report(payload: PulsePayload) -> str:
    lines = [
        "=== Analysis (Phase 3) ===",
        f"week_of:          {payload.week_of}",
        f"window:           {payload.window_start} -> {payload.window_end}",
        f"total_reviews:    {payload.total_reviews}",
        f"by_store:         {payload.by_store}",
        f"themes_all ({len(payload.themes_all)}): "
        + ", ".join(f"{t.id}={t.metrics.count}" for t in payload.themes_all),
        f"themes_top ({len(payload.themes_top)}): "
        + ", ".join(f"{t.id}(score={t.score})" for t in payload.themes_top),
        f"quotes:           {len(payload.quotes)}",
        f"actions:          {len(payload.actions)}",
    ]
    if payload.limitation_note:
        lines.append(f"limitation_note:  {payload.limitation_note}")
    return "\n".join(lines)
