"""Unit tests for Phase 3 theme analysis."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.actions import generate_actions
from src.analysis.clusterer import assign_themes, build_themes
from src.analysis.quotes import select_quotes
from src.analysis.ranker import rank_top_themes, score_themes
from src.models import Review

LABELS = ["onboarding", "kyc", "payments", "statements", "withdrawals"]
TODAY = date(2026, 7, 28)


def _review(id_, store, rating, text, days_ago=0, title=None) -> Review:
    return Review(
        id=id_,
        store=store,
        rating=rating,
        title=title,
        text=text,
        date=TODAY - timedelta(days=days_ago),
        export_key=id_,
    )


def _sample_reviews() -> list[Review]:
    return [
        _review("p1", "app_store", 1, "Card payment declined at checkout again this week", 2),
        _review("p2", "play_store", 2, "UPI payment failed even with sufficient balance", 5),
        _review("p3", "app_store", 1, "Checkout charge failed three times on my card", 10),
        _review("k1", "play_store", 2, "KYC document upload fails with a generic error", 3),
        _review("k2", "app_store", 1, "KYC selfie step loops forever on iPhone", 7),
        _review("o1", "app_store", 2, "Onboarding freezes after phone verification step", 1),
        _review("misc1", "play_store", 5, "Great app overall, love the new dashboard design", 1),
    ]


class ClusterTests(unittest.TestCase):
    def test_theme_cap(self) -> None:
        reviews = _sample_reviews()
        assign_themes(reviews, LABELS)
        themes = build_themes(reviews, window_end=TODAY, theme_max=5)
        self.assertLessEqual(len(themes), 5)

    def test_other_bucket_for_unmatched(self) -> None:
        reviews = _sample_reviews()
        assign_themes(reviews, LABELS)
        misc = next(r for r in reviews if r.id == "misc1")
        self.assertEqual(misc.theme_id, "other")

    def test_payments_and_kyc_assigned(self) -> None:
        reviews = _sample_reviews()
        assign_themes(reviews, LABELS)
        by_id = {r.id: r.theme_id for r in reviews}
        self.assertEqual(by_id["p1"], "payments")
        self.assertEqual(by_id["k1"], "kyc")
        self.assertEqual(by_id["o1"], "onboarding")

    def test_empty_input_yields_no_themes(self) -> None:
        themes = build_themes([], window_end=TODAY, theme_max=5)
        self.assertEqual(themes, [])

    def test_merge_overflow_into_other(self) -> None:
        # 6 distinct single-review themes should collapse to <=5 via merge into "other"
        labels = ["a", "b", "c", "d", "e"]
        reviews = [
            _review("r1", "app_store", 1, "a issue here today", title=None),
            _review("r2", "app_store", 1, "b issue here today"),
            _review("r3", "app_store", 1, "c issue here today"),
            _review("r4", "app_store", 1, "d issue here today"),
            _review("r5", "app_store", 1, "e issue here today"),
            _review("r6", "app_store", 1, "totally unrelated zzz content"),
        ]
        assign_themes(reviews, labels)
        themes = build_themes(reviews, window_end=TODAY, theme_max=5)
        self.assertLessEqual(len(themes), 5)


class RankerTests(unittest.TestCase):
    def test_ranks_by_score_desc(self) -> None:
        reviews = _sample_reviews()
        assign_themes(reviews, LABELS)
        themes = build_themes(reviews, window_end=TODAY, theme_max=5)
        themes = score_themes(themes, reviews)
        top = rank_top_themes(themes, top_n=3)
        self.assertLessEqual(len(top), 3)
        scores = [t.score for t in top]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_top_n_zero_returns_empty(self) -> None:
        self.assertEqual(rank_top_themes([], top_n=3), [])


class QuoteTests(unittest.TestCase):
    def test_quotes_are_verbatim_substrings(self) -> None:
        reviews = _sample_reviews()
        assign_themes(reviews, LABELS)
        themes = build_themes(reviews, window_end=TODAY, theme_max=5)
        themes = score_themes(themes, reviews)
        top = rank_top_themes(themes, top_n=3)
        quotes = select_quotes(top, reviews, target=3)
        texts_by_id = {r.id: r.text for r in reviews}
        for q in quotes:
            self.assertIn(q.text, texts_by_id.values())

    def test_no_more_quotes_than_target(self) -> None:
        reviews = _sample_reviews()
        assign_themes(reviews, LABELS)
        themes = build_themes(reviews, window_end=TODAY, theme_max=5)
        themes = score_themes(themes, reviews)
        top = rank_top_themes(themes, top_n=3)
        quotes = select_quotes(top, reviews, target=3)
        self.assertLessEqual(len(quotes), 3)

    def test_empty_themes_yield_no_quotes(self) -> None:
        self.assertEqual(select_quotes([], [], target=3), [])


class ActionTests(unittest.TestCase):
    def test_actions_grounded_in_top_themes(self) -> None:
        reviews = _sample_reviews()
        assign_themes(reviews, LABELS)
        themes = build_themes(reviews, window_end=TODAY, theme_max=5)
        themes = score_themes(themes, reviews)
        top = rank_top_themes(themes, top_n=3)
        actions = generate_actions(top, target=3)
        top_ids = {t.id for t in top}
        for action in actions:
            self.assertTrue(action.theme_ids)
            for tid in action.theme_ids:
                self.assertIn(tid, top_ids)

    def test_actions_are_distinct(self) -> None:
        reviews = _sample_reviews()
        assign_themes(reviews, LABELS)
        themes = build_themes(reviews, window_end=TODAY, theme_max=5)
        themes = score_themes(themes, reviews)
        top = rank_top_themes(themes, top_n=3)
        actions = generate_actions(top, target=3)
        texts = [a.text for a in actions]
        self.assertEqual(len(texts), len(set(texts)))

    def test_no_themes_yields_no_actions(self) -> None:
        self.assertEqual(generate_actions([], target=3), [])


if __name__ == "__main__":
    unittest.main()
