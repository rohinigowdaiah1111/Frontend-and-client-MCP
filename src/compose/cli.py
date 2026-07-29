"""CLI: run Groq final copy (Phase 4b) from a fact pack JSON."""

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
from src.compose.groq_writer import GroqWriteError, write_final_copy
from src.config import ConfigError, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4b: Groq writes final report + email before Docs/Gmail"
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
        logging.error(
            "Fact pack not found: %s — produce PulsePayload / pulse-facts.json in Phase 4 first",
            facts_path,
        )
        return 1

    fact_pack = load_fact_pack(facts_path)
    try:
        copy, report = write_final_copy(fact_pack, config=config, persist_facts=False)
    except GroqWriteError as exc:
        logging.error("BLOCKED: %s", exc)
        return 1

    print(json.dumps({"ok": report.ok, "model": copy.model, "word_count": copy.word_count}, indent=2))
    print("Wrote output/pulse-latest.md and output/email-latest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
