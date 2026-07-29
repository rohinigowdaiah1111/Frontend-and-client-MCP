"""CLI: Phase 3 theme analysis -> output/pulse-facts.json."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.pipeline import AnalysisBlocked, analyze, format_analysis_report
from src.config import ConfigError, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 3: cluster themes, rank top, pick quotes + actions"
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--anonymized",
        type=Path,
        default=None,
        help="Path to data/processed/anonymized.json (default)",
    )
    parser.add_argument(
        "--from-privacy",
        action="store_true",
        help="Run Phase 1 ingest + Phase 2 privacy first, then analyze in-memory",
    )
    parser.add_argument("--as-of", type=str, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
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
    reviews = None

    if args.from_privacy:
        from src.ingest import ingest
        from src.privacy.pipeline import anonymize

        ingest_result = ingest(config, as_of=as_of, persist=True)
        if ingest_result.blocked:
            logging.error("Ingest blocked: %s", ingest_result.block_reason)
            return 1
        privacy_result = anonymize(ingest_result.reviews, config=config, persist=True)
        if privacy_result.blocked:
            logging.error("Privacy gate blocked: %s", privacy_result.block_reason)
            return 1
        reviews = privacy_result.reviews

    try:
        payload = analyze(
            reviews,
            config=config,
            anonymized_path=args.anonymized,
            as_of=as_of,
            persist=True,
        )
    except AnalysisBlocked as exc:
        logging.error("BLOCKED: %s", exc)
        return 1
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    print(format_analysis_report(payload))
    print("Wrote output/pulse-facts.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
