"""Delivery gate: Docs/Gmail MCP only after successful Groq final copy."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import PulseConfig, load_config
from src.models import DeliveryGateResult, FinalEmail

logger = logging.getLogger(__name__)


class DeliveryBlocked(RuntimeError):
    """Raised when Docs/Gmail must not run."""


def check_delivery_gate(
    config: PulseConfig | None = None,
    *,
    output_dir: Path | None = None,
) -> DeliveryGateResult:
    """
    Allow MCP delivery only when Groq artifacts exist (and require_before_delivery).
    """
    cfg = config or load_config()
    out = output_dir or (cfg.root / "output")
    report_path = out / "pulse-latest.md"
    email_path = out / "email-latest.json"

    if not cfg.groq.require_before_delivery:
        # Explicit opt-out — still prefer Groq artifacts when present
        logger.warning("groq.require_before_delivery is false — delivery gate relaxed")
        return DeliveryGateResult(
            allowed=True,
            reason="require_before_delivery disabled",
            report_path=str(report_path) if report_path.is_file() else None,
            email_path=str(email_path) if email_path.is_file() else None,
        )

    if not cfg.groq.enabled:
        return DeliveryGateResult(
            allowed=False,
            reason="groq.enabled is false while require_before_delivery is true (G-07)",
        )

    if not report_path.is_file():
        return DeliveryGateResult(
            allowed=False,
            reason=f"Missing Groq report at {report_path} (V-04 / O-06). Run Phase 4b first.",
        )
    if not email_path.is_file():
        return DeliveryGateResult(
            allowed=False,
            reason=f"Missing Groq email at {email_path} (V-05 / O-06). Run Phase 4b first.",
        )

    try:
        email = FinalEmail.from_dict(json.loads(email_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return DeliveryGateResult(
            allowed=False,
            reason=f"Malformed Groq email artifact (G-08): {exc}",
        )

    report_body = report_path.read_text(encoding="utf-8")
    if not report_body.strip():
        return DeliveryGateResult(allowed=False, reason="Groq report is empty")
    if not email.body.strip():
        return DeliveryGateResult(allowed=False, reason="Groq email body is empty (M-06)")

    return DeliveryGateResult(
        allowed=True,
        reason=None,
        report_path=str(report_path),
        email_path=str(email_path),
        report_body=report_body,
        email=email,
    )


def require_delivery_ready(
    config: PulseConfig | None = None,
    *,
    output_dir: Path | None = None,
) -> DeliveryGateResult:
    result = check_delivery_gate(config, output_dir=output_dir)
    if not result.allowed:
        raise DeliveryBlocked(result.reason or "Delivery blocked")
    return result


def fill_doc_link(email_body: str, doc_url: str | None) -> str:
    if doc_url:
        return email_body.replace("{doc_link}", doc_url)
    return email_body.replace("{doc_link}", "(doc link unavailable)")
