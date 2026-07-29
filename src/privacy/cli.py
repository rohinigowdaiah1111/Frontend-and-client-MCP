"""CLI: Phase 2 privacy gate (PII redaction)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import ConfigError, load_config
from src.ingest import ingest
from src.privacy.pipeline import anonymize, format_privacy_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2: PII redaction / anonymized corpus")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--canonical",
        type=Path,
        default=None,
        help="Path to data/processed/canonical.json (default)",
    )
    parser.add_argument(
        "--from-ingest",
        action="store_true",
        help="Run Phase 1 ingest first, then redact in-memory",
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="Anchor date for ingest when using --from-ingest (YYYY-MM-DD)",
    )
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

    reviews = None
    if args.from_ingest:
        from datetime import date

        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        ingest_result = ingest(config, as_of=as_of, persist=True)
        if ingest_result.blocked:
            logging.error("Ingest blocked: %s", ingest_result.block_reason)
            return 1
        reviews = ingest_result.reviews

    result = anonymize(
        reviews,
        config=config,
        canonical_path=args.canonical,
        persist=True,
    )
    print(format_privacy_report(result))
    if result.blocked:
        return 1
    print(f"OK: {len(result.reviews)} anonymized reviews")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
