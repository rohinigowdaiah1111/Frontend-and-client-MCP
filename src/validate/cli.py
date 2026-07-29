"""CLI: Phase 4 pre-LLM validation of a fact pack (output/pulse-facts.json)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.compose.facts import load_fact_pack
from src.config import ConfigError, load_config
from src.validate.fact_pack import validate_fact_pack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4: validate a fact pack before Groq is called (Phase 4b)"
    )
    parser.add_argument(
        "--facts",
        type=Path,
        default=None,
        help="Path to pulse-facts.json (default: output/pulse-facts.json)",
    )
    parser.add_argument("--config", type=Path, default=None)
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

    facts_path = args.facts or (config.root / "output" / "pulse-facts.json")
    if not facts_path.is_file():
        logging.error("Fact pack not found: %s — run Phase 3 analysis first", facts_path)
        return 1

    fact_pack = load_fact_pack(facts_path)
    report = validate_fact_pack(fact_pack, config=config)

    diag_path = facts_path.parent / "pulse-facts.validation.json"
    diag_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report.to_dict(), indent=2))
    if not report.ok:
        print(f"BLOCKED: fix errors before running Phase 4b. See {diag_path}")
        return 1
    print(f"OK: fact pack passed pre-LLM validation ({diag_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
