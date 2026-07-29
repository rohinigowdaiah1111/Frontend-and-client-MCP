"""Unit tests for client-side Groq rate-limit awareness."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.compose.rate_limit import (
    GroqUsageTracker,
    TokenBudgetExceeded,
    clamp_max_tokens,
    estimate_tokens,
)


class EstimateTokensTests(unittest.TestCase):
    def test_empty_string_is_zero(self) -> None:
        self.assertEqual(estimate_tokens(""), 0)

    def test_scales_with_length(self) -> None:
        short = estimate_tokens("hello world")
        long = estimate_tokens("hello world " * 50)
        self.assertGreater(long, short)


class ClampMaxTokensTests(unittest.TestCase):
    def test_fits_within_budget(self) -> None:
        result = clamp_max_tokens(prompt_tokens=200, configured_max_tokens=700, tpm=1000)
        self.assertLessEqual(result, 700)
        self.assertGreaterEqual(result, 150)

    def test_uses_configured_max_when_budget_is_generous(self) -> None:
        result = clamp_max_tokens(prompt_tokens=50, configured_max_tokens=300, tpm=1000)
        self.assertEqual(result, 300)

    def test_raises_when_prompt_alone_exceeds_budget(self) -> None:
        with self.assertRaises(TokenBudgetExceeded):
            clamp_max_tokens(prompt_tokens=950, configured_max_tokens=700, tpm=1000)


class GroqUsageTrackerTests(unittest.TestCase):
    def test_record_and_check_within_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "groq-usage.json"
            tracker = GroqUsageTracker(path)
            tracker.check_daily_budget(rpd=30, tpd=100000)  # should not raise, empty log
            tracker.record(prompt_tokens=500, completion_tokens=300)
            tracker.check_daily_budget(rpd=30, tpd=100000)  # still fine after 1 call

    def test_blocks_when_daily_request_budget_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "groq-usage.json"
            tracker = GroqUsageTracker(path)
            for _ in range(3):
                tracker.record(prompt_tokens=100, completion_tokens=50)
            with self.assertRaises(TokenBudgetExceeded):
                tracker.check_daily_budget(rpd=3, tpd=100000)

    def test_blocks_when_daily_token_budget_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "groq-usage.json"
            tracker = GroqUsageTracker(path)
            tracker.record(prompt_tokens=600, completion_tokens=500)
            with self.assertRaises(TokenBudgetExceeded):
                tracker.check_daily_budget(rpd=100, tpd=1000)


if __name__ == "__main__":
    unittest.main()
