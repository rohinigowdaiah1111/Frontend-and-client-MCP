"""PII detection / redaction patterns (shared by privacy + validators)."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"
)
HANDLE_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,}\b")
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.I,
)
# 15-digit IMEI-like sequences
IMEI_RE = re.compile(r"\b\d{15}\b")
# Long hex device tokens (8+ hex chars, not part of normal words)
HEX_TOKEN_RE = re.compile(r"\b(?:0x)?[0-9a-f]{12,}\b", re.I)
# Best-effort first-person name introductions (P-04)
FIRST_PERSON_NAME_RE = re.compile(
    r"\b((?:I['’]m|I am|My name is)\s+)([A-Z][a-z]{1,24})\b"
)

PLACEHOLDERS = {
    "email": "[email]",
    "phone": "[phone]",
    "handle": "[handle]",
    "uuid": "[device_id]",
    "imei": "[device_id]",
    "hex_token": "[device_id]",
    "name": "[name]",
}

DEFAULT_STRIP_FIELDS = (
    "username",
    "author",
    "email",
    "device_id",
    "reviewer_name",
    "reviewer",
    "user",
    "user_name",
    "name",
)
