"""Groq LLM writer — final report + final email before Docs/Gmail MCP."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.compose.facts import extract_quotes, write_fact_pack
from src.compose.prompts import SYSTEM_PROMPT, build_user_prompt
from src.compose.rate_limit import (
    GroqUsageTracker,
    TokenBudgetExceeded,
    clamp_max_tokens,
    estimate_tokens,
    sleep_for_retry,
)
from src.config import PulseConfig, load_config
from src.models import FinalEmail, GroqFinalCopy, ValidationReport
from src.validate.checks import validate_final_copy, word_count
from src.validate.fact_pack import validate_fact_pack

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)
_MAX_RATE_LIMIT_RETRIES = 3


class GroqWriteError(RuntimeError):
    """Groq final copy could not be produced."""


def _parse_llm_json(content: str) -> dict[str, Any]:
    text = content.strip()
    fence = _JSON_FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
        else:
            raise
    if not isinstance(data, dict):
        raise GroqWriteError("Groq response JSON must be an object")
    return data


def _call_groq(
    config: PulseConfig,
    *,
    system: str,
    user: str,
    usage_tracker: GroqUsageTracker,
) -> str:
    api_key = config.groq.resolve_api_key()
    if not api_key:
        raise GroqWriteError(
            f"Missing API key in env var {config.groq.api_key_env} (edge-case G-01). "
            "Set it before Phase 4b / delivery."
        )
    if not config.groq.enabled:
        raise GroqWriteError("groq.enabled is false")

    try:
        from groq import Groq, RateLimitError
    except ImportError as exc:
        raise GroqWriteError(
            "groq package not installed. Run: pip install -r requirements.txt"
        ) from exc

    limits = config.groq.limits

    # Daily budget: best-effort, based only on what this pipeline has logged itself.
    try:
        usage_tracker.check_daily_budget(rpd=limits.rpd, tpd=limits.tpd)
    except TokenBudgetExceeded as exc:
        raise GroqWriteError(str(exc)) from exc

    # Per-minute token budget: a prompt too large to fit will never succeed by retrying.
    prompt_tokens_est = estimate_tokens(system) + estimate_tokens(user)
    try:
        max_tokens = clamp_max_tokens(
            prompt_tokens=prompt_tokens_est,
            configured_max_tokens=config.groq.max_tokens,
            tpm=limits.tpm,
        )
    except TokenBudgetExceeded as exc:
        raise GroqWriteError(str(exc)) from exc

    client = Groq(api_key=api_key)

    for rl_attempt in range(_MAX_RATE_LIMIT_RETRIES):
        try:
            response = client.chat.completions.create(
                model=config.groq.model,
                temperature=config.groq.temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            break
        except RateLimitError as exc:
            retry_after = None
            response_obj = getattr(exc, "response", None)
            if response_obj is not None:
                header = response_obj.headers.get("retry-after")
                if header:
                    try:
                        retry_after = float(header)
                    except ValueError:
                        retry_after = None
            if rl_attempt == _MAX_RATE_LIMIT_RETRIES - 1:
                raise GroqWriteError(
                    f"Groq rate limit exceeded after {_MAX_RATE_LIMIT_RETRIES} attempts "
                    f"(rpm={limits.rpm}, tpm={limits.tpm}): {exc}"
                ) from exc
            sleep_for_retry(rl_attempt, retry_after=retry_after)
    else:  # pragma: no cover - loop always breaks or raises above
        raise GroqWriteError("Groq rate limit retry loop exhausted unexpectedly")

    content = response.choices[0].message.content
    if not content:
        raise GroqWriteError("Empty response from Groq")

    usage = getattr(response, "usage", None)
    usage_tracker.record(
        prompt_tokens=getattr(usage, "prompt_tokens", prompt_tokens_est) if usage else prompt_tokens_est,
        completion_tokens=getattr(usage, "completion_tokens", 0) if usage else word_count(content),
    )
    return content


def persist_final_copy(copy: GroqFinalCopy, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "pulse-latest.md"
    email_path = output_dir / "email-latest.json"
    report_path.write_text(copy.report_markdown.strip() + "\n", encoding="utf-8")
    email_path.write_text(json.dumps(copy.email.to_dict(), indent=2) + "\n", encoding="utf-8")
    meta_path = output_dir / "groq-meta.json"
    meta_path.write_text(json.dumps(copy.to_dict(), indent=2) + "\n", encoding="utf-8")
    return report_path, email_path


def write_final_copy(
    fact_pack: dict[str, Any],
    *,
    config: PulseConfig | None = None,
    output_dir: Path | None = None,
    persist_facts: bool = True,
) -> tuple[GroqFinalCopy, ValidationReport]:
    """
    Phase 4 gate + Phase 4b Groq call.

    Runs the pre-LLM Constraint Validator (Phase 4) first; hard failures block
    Groq entirely (no API call, no partial artifacts) and write a diagnostic.
    Only then calls Groq to produce final report + email, validates the result,
    and retries once on soft failures. Does not call Docs/Gmail MCP.
    """
    cfg = config or load_config()
    root = cfg.root
    out = output_dir or (root / "output")

    if persist_facts:
        write_fact_pack(fact_pack, out / "pulse-facts.json")

    pre_check = validate_fact_pack(fact_pack, config=cfg)
    if not pre_check.ok:
        out.mkdir(parents=True, exist_ok=True)
        diag_path = out / "pulse-facts.validation.json"
        diag_path.write_text(json.dumps(pre_check.to_dict(), indent=2) + "\n", encoding="utf-8")
        raise GroqWriteError(
            "Phase 4 pre-LLM validation failed — Groq was not called: "
            + "; ".join(pre_check.errors)
        )
    if pre_check.warnings:
        for warning in pre_check.warnings:
            logger.warning("Pre-LLM validation warning: %s", warning)

    quotes = extract_quotes(fact_pack)
    max_words = cfg.pulse.max_words
    last_report = ValidationReport(ok=False, errors=["not started"])
    copy: GroqFinalCopy | None = None
    usage_tracker = GroqUsageTracker(out / "groq-usage.json")

    for attempt in range(2):
        stricter = attempt > 0
        user = build_user_prompt(fact_pack, max_words=max_words, stricter=stricter)
        try:
            raw = _call_groq(cfg, system=SYSTEM_PROMPT, user=user, usage_tracker=usage_tracker)
            data = _parse_llm_json(raw)
        except Exception as exc:  # noqa: BLE001
            logger.error("Groq call failed (attempt %s): %s", attempt + 1, exc)
            last_report = ValidationReport(ok=False, errors=[str(exc)])
            # A too-large prompt or an exhausted daily budget will not improve on
            # a retry — fail fast instead of burning the second attempt.
            if isinstance(exc, GroqWriteError) and (
                "token budget" in str(exc).lower() or "usage log" in str(exc).lower()
            ):
                raise
            if attempt == 0:
                continue
            raise GroqWriteError(str(exc)) from exc

        report = str(data.get("report_markdown") or "").strip()
        subject = str(data.get("email_subject") or data.get("subject") or "").strip()
        body = str(data.get("email_body") or data.get("body") or "").strip()
        if not subject:
            subject = "Weekly Review Pulse"
        copy = GroqFinalCopy(
            report_markdown=report,
            email=FinalEmail(subject=subject, body=body),
            model=cfg.groq.model,
            word_count=word_count(report),
            retries=attempt,
        )
        last_report = validate_final_copy(
            report=copy.report_markdown,
            email_body=copy.email.body,
            quotes=quotes,
            max_words=max_words,
            allow_sparse=cfg.pulse.allow_sparse,
        )
        if last_report.ok:
            persist_final_copy(copy, out)
            logger.info(
                "Groq final copy OK (model=%s words=%s retries=%s)",
                copy.model,
                copy.word_count,
                copy.retries,
            )
            return copy, last_report
        logger.warning("Groq validation failed (attempt %s): %s", attempt + 1, last_report.errors)

    # Persist last attempt for debugging even on failure
    if copy is not None:
        persist_final_copy(copy, out)
    raise GroqWriteError(
        "Groq final copy failed post-LLM validation: " + "; ".join(last_report.errors)
    )
