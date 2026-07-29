"""Load and validate config/pulse.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config" / "pulse.yaml"

# Secrets (e.g. GROQ_API_KEY) live only in the environment / .env — never in
# pulse.yaml or source. Loading .env here means the app reads the secret
# straight off disk into its own process; nothing upstream of this needs to
# see or handle the value. override=False so real shell/session env vars
# (e.g. set by an operator or CI) always win over a stale .env.
load_dotenv(ROOT / ".env", override=False)

WINDOW_MIN = 8
WINDOW_MAX = 12


@dataclass(frozen=True)
class StoreSource:
    name: str  # app_store | play_store
    path: Path
    enabled: bool


@dataclass(frozen=True)
class GroqLimits:
    """Best-effort client-side view of Groq's published rate limits for the configured model."""

    rpm: int
    tpm: int
    rpd: int
    tpd: int


@dataclass(frozen=True)
class GroqSettings:
    enabled: bool
    model: str
    api_key_env: str
    temperature: float
    max_tokens: int
    require_before_delivery: bool
    limits: GroqLimits

    def resolve_api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) or None


@dataclass(frozen=True)
class DeliverySettings:
    docs_title_pattern: str
    gmail_to: str
    gmail_subject_pattern: str
    include_doc_link: bool
    include_full_body: bool


@dataclass(frozen=True)
class PulseSettings:
    top_themes: int
    quotes: int
    actions: int
    max_words: int
    allow_sparse: bool


@dataclass(frozen=True)
class PulseConfig:
    window_weeks: int
    sources: list[StoreSource]
    groq: GroqSettings
    delivery: DeliverySettings
    pulse: PulseSettings
    privacy_strip_fields: list[str]
    theme_labels: list[str]
    theme_max: int
    raw: dict[str, Any]
    path: Path

    @property
    def root(self) -> Path:
        return self.path.resolve().parents[1]


class ConfigError(ValueError):
    """Invalid or missing pipeline configuration."""


def load_config(path: Path | None = None) -> PulseConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(f"Missing config: {config_path}")

    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    window_weeks = int(raw.get("window_weeks", 10))
    if window_weeks < WINDOW_MIN or window_weeks > WINDOW_MAX:
        raise ConfigError(
            f"window_weeks must be between {WINDOW_MIN} and {WINDOW_MAX} (got {window_weeks})"
        )

    root = config_path.resolve().parents[1]
    sources_raw = raw.get("sources") or {}
    sources: list[StoreSource] = []
    for name in ("app_store", "play_store"):
        entry = sources_raw.get(name) or {}
        rel = entry.get("path")
        if not rel:
            continue
        sources.append(
            StoreSource(
                name=name,
                path=(root / rel).resolve() if not Path(rel).is_absolute() else Path(rel),
                enabled=bool(entry.get("enabled", True)),
            )
        )

    if not sources:
        raise ConfigError("No sources configured under sources.app_store / sources.play_store")

    groq_raw = raw.get("groq") or {}
    limits_raw = groq_raw.get("limits") or {}
    groq_limits = GroqLimits(
        rpm=int(limits_raw.get("rpm", 30)),
        tpm=int(limits_raw.get("tpm", 1000)),
        rpd=int(limits_raw.get("rpd", 12000)),
        tpd=int(limits_raw.get("tpd", 100000)),
    )
    groq = GroqSettings(
        enabled=bool(groq_raw.get("enabled", True)),
        model=str(groq_raw.get("model", "llama-3.3-70b-versatile")),
        api_key_env=str(groq_raw.get("api_key_env", "GROQ_API_KEY")),
        temperature=float(groq_raw.get("temperature", 0.2)),
        max_tokens=int(groq_raw.get("max_tokens", 700)),
        require_before_delivery=bool(groq_raw.get("require_before_delivery", True)),
        limits=groq_limits,
    )
    if groq.require_before_delivery and not groq.enabled:
        raise ConfigError(
            "Invalid config: groq.require_before_delivery is true but groq.enabled is false (G-07)"
        )

    delivery_raw = raw.get("delivery") or {}
    docs_raw = delivery_raw.get("docs") or {}
    gmail_raw = delivery_raw.get("gmail") or {}
    delivery = DeliverySettings(
        docs_title_pattern=str(docs_raw.get("title_pattern", "Weekly Review Pulse — {iso_week}")),
        gmail_to=str(gmail_raw.get("to", "you@example.com")),
        gmail_subject_pattern=str(
            gmail_raw.get("subject_pattern", "Weekly Review Pulse — {iso_week}")
        ),
        include_doc_link=bool(gmail_raw.get("include_doc_link", True)),
        include_full_body=bool(gmail_raw.get("include_full_body", True)),
    )

    pulse_raw = raw.get("pulse") or {}
    pulse = PulseSettings(
        top_themes=int(pulse_raw.get("top_themes", 3)),
        quotes=int(pulse_raw.get("quotes", 3)),
        actions=int(pulse_raw.get("actions", 3)),
        max_words=int(pulse_raw.get("max_words", 250)),
        allow_sparse=bool(pulse_raw.get("allow_sparse", True)),
    )

    themes_raw = raw.get("themes") or {}
    privacy_raw = raw.get("privacy") or {}

    theme_max = int(themes_raw.get("max", 5))
    theme_labels = list(themes_raw.get("labels") or [])
    if not theme_labels:
        raise ConfigError("themes.labels must not be empty (T-06); add at least one theme label")
    if len(theme_labels) > theme_max:
        raise ConfigError(
            f"themes.labels has {len(theme_labels)} entries, exceeding themes.max={theme_max} (T-05)"
        )

    return PulseConfig(
        window_weeks=window_weeks,
        sources=sources,
        groq=groq,
        delivery=delivery,
        pulse=pulse,
        privacy_strip_fields=list(privacy_raw.get("strip_fields") or []),
        theme_labels=theme_labels,
        theme_max=theme_max,
        raw=raw,
        path=config_path,
    )
