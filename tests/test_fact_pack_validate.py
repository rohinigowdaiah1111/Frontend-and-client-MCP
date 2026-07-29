"""Unit tests for Phase 4 pre-LLM fact pack validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.validate.fact_pack import validate_fact_pack

CONFIG = load_config()
# Isolate from the repo's real anonymized.json (test quotes are fictional, not
# actually verbatim in that corpus); tests that care about the verbatim check
# supply their own temp corpus explicitly.
NO_CORPUS = Path("__no_such_corpus__.json")


def _valid_fact_pack() -> dict:
    return {
        "stats": {"total_reviews": 6, "by_store": {"app_store": 3, "play_store": 3}},
        "themes_all": [{"id": "payments", "label": "Payments"}],
        "themes_top": [{"id": "payments", "label": "Payments"}],
        "quotes": [{"text": "Card payment declined at checkout", "theme_id": "payments"}],
        "actions": [{"text": "Investigate checkout failures", "theme_ids": ["payments"]}],
    }


class FactPackValidateTests(unittest.TestCase):
    def test_valid_pack_passes(self) -> None:
        report = validate_fact_pack(_valid_fact_pack(), config=CONFIG, anonymized_path=NO_CORPUS)
        self.assertTrue(report.ok, report.errors)

    def test_blocks_on_pii_in_quote(self) -> None:
        pack = _valid_fact_pack()
        pack["quotes"] = [{"text": "email me at test@example.com", "theme_id": "payments"}]
        report = validate_fact_pack(pack, config=CONFIG, anonymized_path=NO_CORPUS)
        self.assertFalse(report.ok)
        self.assertTrue(any("PII" in e for e in report.errors))

    def test_blocks_on_ungrounded_action(self) -> None:
        pack = _valid_fact_pack()
        pack["actions"] = [{"text": "Do something", "theme_ids": []}]
        report = validate_fact_pack(pack, config=CONFIG, anonymized_path=NO_CORPUS)
        self.assertFalse(report.ok)
        self.assertTrue(any("A-03" in e for e in report.errors))

    def test_blocks_on_unknown_theme_reference(self) -> None:
        pack = _valid_fact_pack()
        pack["actions"] = [{"text": "Fix it", "theme_ids": ["not-a-real-theme"]}]
        report = validate_fact_pack(pack, config=CONFIG, anonymized_path=NO_CORPUS)
        self.assertFalse(report.ok)
        self.assertTrue(any("unknown theme_ids" in e for e in report.errors))

    def test_blocks_on_stats_mismatch(self) -> None:
        pack = _valid_fact_pack()
        pack["stats"] = {"total_reviews": 10, "by_store": {"app_store": 3, "play_store": 3}}
        report = validate_fact_pack(pack, config=CONFIG, anonymized_path=NO_CORPUS)
        self.assertFalse(report.ok)
        self.assertTrue(any("V-03" in e for e in report.errors))

    def test_blocks_on_theme_cap_exceeded(self) -> None:
        pack = _valid_fact_pack()
        pack["themes_all"] = [{"id": f"t{i}", "label": f"Theme {i}"} for i in range(CONFIG.theme_max + 1)]
        report = validate_fact_pack(pack, config=CONFIG, anonymized_path=NO_CORPUS)
        self.assertFalse(report.ok)
        self.assertTrue(any("themes_all" in e for e in report.errors))

    def test_sparse_shortfall_is_warning_when_allow_sparse(self) -> None:
        pack = _valid_fact_pack()
        pack["quotes"] = []
        pack["actions"] = []
        report = validate_fact_pack(pack, config=CONFIG, anonymized_path=NO_CORPUS)
        if CONFIG.pulse.allow_sparse:
            self.assertTrue(report.ok, report.errors)
            self.assertTrue(any("quotes" in w for w in report.warnings))
        else:
            self.assertFalse(report.ok)

    def test_verbatim_check_flags_non_matching_quote(self, tmp_path: Path | None = None) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            anon_path = Path(tmp) / "anonymized.json"
            anon_path.write_text(
                json.dumps({"reviews": [{"text": "Card payment declined at checkout"}]}),
                encoding="utf-8",
            )
            pack = _valid_fact_pack()
            pack["quotes"] = [{"text": "This quote was never actually said", "theme_id": "payments"}]
            report = validate_fact_pack(pack, config=CONFIG, anonymized_path=anon_path)
            self.assertFalse(report.ok)
            self.assertTrue(any("verbatim" in e for e in report.errors))


if __name__ == "__main__":
    unittest.main()
