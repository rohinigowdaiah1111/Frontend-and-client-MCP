"""Unit tests for Phase 2 PII redactor."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models import Review
from src.privacy.redactor import (
    RedactionError,
    drop_strip_fields,
    find_pii_kinds,
    redact_review,
    redact_text,
)


def _review(text: str, title: str | None = None) -> Review:
    return Review(
        id="abc123",
        store="app_store",
        rating=2,
        title=title,
        text=text,
        date=date(2026, 7, 1),
        export_key="as-1",
    )


class RedactorTests(unittest.TestCase):
    def test_email(self) -> None:
        out = redact_text("Contact me at user@example.com please")
        self.assertIn("[email]", out)
        self.assertNotIn("user@example.com", out)
        self.assertNotIn("email", find_pii_kinds(out))

    def test_phone(self) -> None:
        out = redact_text("Call 415-555-1234 about this bug")
        self.assertIn("[phone]", out)
        self.assertNotIn("415-555-1234", out)

    def test_handle(self) -> None:
        out = redact_text("Contact me @jane_doe on twitter")
        self.assertIn("[handle]", out)
        self.assertNotIn("@jane_doe", out)

    def test_uuid_device(self) -> None:
        out = redact_text("device 550e8400-e29b-41d4-a716-446655440000 crashed")
        self.assertIn("[device_id]", out)
        self.assertNotIn("550e8400-e29b-41d4-a716-446655440000", out)

    def test_imei(self) -> None:
        out = redact_text("IMEI 490154203237518 is weird")
        self.assertIn("[device_id]", out)
        self.assertNotIn("490154203237518", out)

    def test_first_person_name(self) -> None:
        out = redact_text("I'm Sarah and the app crashes")
        self.assertIn("I'm [name]", out)
        self.assertNotIn("Sarah", out)

    def test_drop_strip_fields(self) -> None:
        row = drop_strip_fields(
            {"text": "hi", "username": "bob", "email": "a@b.com", "rating": 3}
        )
        self.assertNotIn("username", row)
        self.assertNotIn("email", row)
        self.assertEqual(row["text"], "hi")

    def test_redact_review_preserves_non_pii(self) -> None:
        r = redact_review(
            _review("Payment failed on checkout", title="Payments broken")
        )
        self.assertEqual(r.text, "Payment failed on checkout")
        self.assertEqual(r.title, "Payments broken")
        self.assertEqual(r.export_key, "as-1")

    def test_redact_review_scrubs_title_and_text(self) -> None:
        r = redact_review(
            _review(
                "Email me at a@b.co about KYC",
                title="Help @support_team",
            )
        )
        self.assertIn("[email]", r.text)
        self.assertIn("[handle]", r.title or "")
        self.assertEqual([], [k for k in find_pii_kinds(r.text) if k != "name"])

    def test_no_identity_fields_in_dict(self) -> None:
        r = redact_review(_review("fine"))
        keys = set(r.to_dict())
        for banned in ("username", "author", "email", "device_id"):
            self.assertNotIn(banned, keys)


if __name__ == "__main__":
    unittest.main()
