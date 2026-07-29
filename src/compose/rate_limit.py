"""Client-side Groq rate-limit awareness (RPM / TPM / RPD / TPD) — best effort.

Groq enforces these limits server-side; this module exists to avoid *doomed*
requests (a prompt that alone exceeds the per-minute token budget will never
succeed, no matter how many times we retry) and to fail closed once a local
usage log shows we've likely exhausted a daily quota, rather than hammering
the API and burning retries on guaranteed 429s.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TokenBudgetExceeded(RuntimeError):
    """A request cannot fit the configured rate limits — do not call the API."""


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate (~4 chars/token for English text). This is a
    conservative heuristic, not an exact tokenizer count — actual usage
    comes back on `response.usage` after a real call and is what gets
    recorded by `GroqUsageTracker.record`.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def clamp_max_tokens(
    *,
    prompt_tokens: int,
    configured_max_tokens: int,
    tpm: int,
    min_useful_tokens: int = 150,
    safety_margin: float = 0.85,
) -> int:
    """
    Fit the completion token budget under the per-minute token limit (TPM).

    Raises TokenBudgetExceeded when the prompt alone leaves no useful room —
    that means the fact pack must be shrunk, since no amount of retrying
    will make a too-large prompt fit a fixed per-minute budget.
    """
    budget = int(tpm * safety_margin) - prompt_tokens
    if budget < min_useful_tokens:
        raise TokenBudgetExceeded(
            f"Estimated prompt is ~{prompt_tokens} tokens, leaving only ~{budget} of the "
            f"{tpm}/min token budget (need >= {min_useful_tokens} for a useful completion). "
            "Shrink the fact pack sent to Groq before retrying — retrying as-is will not help."
        )
    return max(min_useful_tokens, min(configured_max_tokens, budget))


def sleep_for_retry(attempt: int, *, retry_after: float | None, cap_seconds: float = 65.0) -> None:
    """Back off before a Groq retry: honor Retry-After if the API gave one, else exponential backoff."""
    delay = retry_after if retry_after and retry_after > 0 else min(cap_seconds, 2.0**attempt)
    delay = min(delay, cap_seconds)
    logger.warning("Groq rate limited — sleeping %.1fs before retry", delay)
    time.sleep(delay)


@dataclass
class UsageEntry:
    ts: str
    prompt_tokens: int
    completion_tokens: int


class GroqUsageTracker:
    """
    Best-effort local daily usage log (`output/groq-usage.json`) for RPD/TPD
    circuit-breaking. This cannot see Groq's true server-side counters — it
    only knows what *this* pipeline has recorded — but for a weekly batch job
    it is enough to stop a runaway retry loop from spending quota we know
    (from our own log) is already gone for the day.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read Groq usage log at %s — treating as empty", self.path)
            return []

    def _today_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        today = date.today().isoformat()
        return [e for e in entries if str(e.get("ts", "")).startswith(today)]

    def check_daily_budget(self, *, rpd: int, tpd: int) -> None:
        today = self._today_entries(self._load())
        used_requests = len(today)
        used_tokens = sum(
            int(e.get("prompt_tokens", 0)) + int(e.get("completion_tokens", 0)) for e in today
        )
        if used_requests >= rpd:
            raise TokenBudgetExceeded(
                f"Local usage log already shows {used_requests} Groq request(s) today (rpd={rpd}). "
                "Refusing to call Groq again until tomorrow (best-effort client-side guard; "
                f"see {self.path})."
            )
        if used_tokens >= tpd:
            raise TokenBudgetExceeded(
                f"Local usage log already shows {used_tokens} Groq token(s) used today (tpd={tpd}). "
                f"Refusing to call Groq again until tomorrow (see {self.path})."
            )

    def record(self, *, prompt_tokens: int, completion_tokens: int) -> None:
        entries = self._load()
        entries.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        )
        entries = entries[-500:]  # keep the log small; ~500 calls is generous for a weekly job
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
