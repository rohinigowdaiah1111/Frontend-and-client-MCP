"""Action Ideator — concrete next steps grounded in ranked themes (§6 rules)."""

from __future__ import annotations

from src.models import ActionItem, Theme

# theme_id -> (fix template for low-rated themes, monitor template for well-rated themes)
ACTION_TEMPLATES: dict[str, tuple[str, str]] = {
    "onboarding": (
        "Fix onboarding flow interruptions (freezes/permission loops) reported this week; "
        "add timeout recovery on first run.",
        "Keep the onboarding flow stable; monitor completion rate for regressions after each release.",
    ),
    "kyc": (
        "Show specific KYC rejection reasons and a pending-status ETA instead of a generic error screen.",
        "Maintain current KYC approval speed; track rejection-reason clarity in upcoming reviews.",
    ),
    "payments": (
        "Add payment decline reason codes and a retry CTA at checkout to reduce failed-charge complaints.",
        "Sustain payment reliability; watch for new decline patterns by day-of-week or platform.",
    ),
    "statements": (
        "Fix statement export gaps (missing transactions/columns) and reconcile displayed balances.",
        "Keep statement accuracy stable; verify balance reconciliation after each release.",
    ),
    "withdrawals": (
        "Clarify withdrawal ETA vs. actual processing time and notify users on holds or cancellations.",
        "Maintain current withdrawal speed; monitor for delay spikes after infrastructure changes.",
    ),
}

SECOND_ANGLE: dict[str, str] = {
    "onboarding": "Add an in-app support prompt for users stuck mid-onboarding for more than 2 minutes.",
    "kyc": "Send proactive status-update notifications during KYC review instead of a blank pending screen.",
    "payments": "Surface a clear retry option immediately after a declined payment instead of a silent failure.",
    "statements": "Add a manual 'refresh statement' action so users can retry failed PDF/CSV generation.",
    "withdrawals": "Publish a real-time withdrawal status tracker instead of a static ETA estimate.",
}

GENERIC_FIX = "Investigate recurring complaints in the '{label}' theme reported this week and prioritize a fix."
GENERIC_MONITOR = "Continue monitoring the '{label}' theme; no urgent fix indicated by this week's signal."
GENERIC_FOLLOWUP = "Take a closer look at '{label}' feedback with an additional review sample next week."


def _is_negative(theme: Theme) -> bool:
    return theme.metrics.avg_rating is None or theme.metrics.avg_rating <= 3.0


def _primary_action_text(theme: Theme) -> str:
    templates = ACTION_TEMPLATES.get(theme.id)
    if templates:
        fix, monitor = templates
        return fix if _is_negative(theme) else monitor
    return (GENERIC_FIX if _is_negative(theme) else GENERIC_MONITOR).format(label=theme.label)


def generate_actions(themes_top: list[Theme], *, target: int) -> list[ActionItem]:
    """
    Produce up to `target` concrete actions, each grounded in >=1 top theme (A-03).
    If fewer than target themes exist, adds distinct secondary angles (A-01) rather
    than inventing ungrounded actions. Never emits vague or duplicate text (A-04/A-05).
    """
    if target <= 0 or not themes_top:
        return []

    actions: list[ActionItem] = []
    seen: set[str] = set()

    for theme in themes_top:
        if len(actions) >= target:
            break
        text = _primary_action_text(theme)
        if text not in seen:
            actions.append(ActionItem(text=text, theme_ids=[theme.id]))
            seen.add(text)

    # A-01: fewer themes than target -> add secondary angles on the richest theme(s)
    themes_sorted = sorted(themes_top, key=lambda t: -t.metrics.count)
    guard = 0
    idx = 0
    while len(actions) < target and themes_sorted and guard < target * len(themes_sorted) + 5:
        guard += 1
        theme = themes_sorted[idx % len(themes_sorted)]
        idx += 1
        text = SECOND_ANGLE.get(theme.id, GENERIC_FOLLOWUP.format(label=theme.label))
        if text not in seen:
            actions.append(ActionItem(text=text, theme_ids=[theme.id]))
            seen.add(text)

    return actions[:target]
