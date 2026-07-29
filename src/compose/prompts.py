"""Prompt templates for Groq final report + email."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You write stakeholder-facing weekly Groww app review pulses
(Groww is the product; reviews come from its App Store and Play Store listings).
Hard rules:
- Use ONLY the provided fact pack. Do not invent themes, quotes, ratings, or actions.
- Quotes must appear EXACTLY as given (verbatim). Do not paraphrase quotes.
- No PII: no names, emails, phones, usernames, device IDs.
- Keep the REPORT at or under the stated max_words.
- Be scannable: short sections, bullets preferred.
- If the fact pack is empty/sparse, say so clearly; do not invent signal.
- email_subject must start with "Weekly Groww Review Pulse".
Respond with ONE JSON object only — no markdown fences, no text outside the JSON — with
exactly these keys: report_markdown (a markdown-formatted string), email_subject, email_body.
Put the literal {doc_link} placeholder inside email_body where the Google Doc URL goes.
"""


def compact_fact_pack_for_prompt(fact_pack: dict[str, Any]) -> dict[str, Any]:
    """
    Strip fields Groq doesn't need to write the report/email (review_ids,
    the full themes_all breakdown) to keep the prompt small. Groq's free-tier
    TPM budget can be as low as ~1000 tokens/minute for a single request, so
    trimming the prompt is not optional — it's what makes a call fit at all.
    """

    def _slim_theme(theme: dict[str, Any]) -> dict[str, Any]:
        metrics = theme.get("metrics") or {}
        return {
            "id": theme.get("id"),
            "label": theme.get("label"),
            "count": metrics.get("count"),
            "avg_rating": metrics.get("avg_rating"),
        }

    themes_top = [_slim_theme(t) for t in (fact_pack.get("themes_top") or [])]
    themes_all = fact_pack.get("themes_all") or []

    return {
        "week_of": fact_pack.get("week_of"),
        "window": fact_pack.get("window"),
        "stats": fact_pack.get("stats"),
        "theme_count_all": len(themes_all),
        "themes_top": themes_top,
        "quotes": [
            {"text": q.get("text"), "theme_id": q.get("theme_id")}
            for q in (fact_pack.get("quotes") or [])
        ],
        "actions": [
            {"text": a.get("text"), "theme_ids": a.get("theme_ids")}
            for a in (fact_pack.get("actions") or [])
        ],
        "limitation_note": fact_pack.get("limitation_note"),
    }


def build_user_prompt(fact_pack: dict[str, Any], *, max_words: int, stricter: bool = False) -> str:
    extra = ""
    if stricter:
        extra = (
            "\nSTRICT RETRY: Previous output failed validation. "
            "Shorten the report, keep every quote character-for-character, "
            "and remove anything that looks like PII.\n"
        )
    compact = compact_fact_pack_for_prompt(fact_pack)
    return (
        f"{extra}"
        f"max_words for report_markdown: {max_words}\n"
        f"fact_pack JSON:\n{json.dumps(compact, separators=(',', ':'))}\n"
        "report_markdown value should use this outline (it is a string INSIDE the JSON, "
        "not your top-level response):\n"
        "Weekly Groww Review Pulse — {week_of}\n"
        "Window: ... | N reviews (AS: a, PS: p)\n"
        "Top themes\n"
        "What users said (verbatim quotes)\n"
        "Suggested next steps\n"
    )
