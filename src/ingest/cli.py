"""CLI: run Phase 1 ingest & normalize."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

# Allow `python -m src.ingest.cli` from repo root
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import ConfigError, load_config
from src.ingest.pipeline import format_metrics_report, ingest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1: ingest & normalize public store reviews")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to pulse.yaml (default: config/pulse.yaml)",
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="Anchor date YYYY-MM-DD for window (default: today)",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not write data/processed/canonical.json",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        logging.error("%s", exc)
        return 2

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    result = ingest(config, as_of=as_of, persist=not args.no_persist)

    print(format_metrics_report(result.metrics))
    if result.blocked:
        print(f"BLOCKED: {result.block_reason}")
        return 1

    print(f"OK: {len(result.reviews)} canonical reviews in window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
