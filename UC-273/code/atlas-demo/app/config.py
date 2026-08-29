"""Runtime configuration and guardrail feature flags.

Every guardrail is a flag so the presenter can show the exact same attack with the
control OFF (it succeeds) and ON (it is blocked). Flags come from the environment at
deploy time, but each API request may override them via a `guardrails` object so the
before/after toggle is instant on a single running Cloud Run revision — no redeploy.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Guardrail flags — the switches each demo toggles.
GUARDRAIL_FLAGS = (
    "enable_model_armor",   # Demo 1: prompt-injection / jailbreak / data-leak scanning
    "enable_dlp_redaction",  # Demo 1: redact PII before it leaves the agent
    "enable_shieldgemma",    # Demo 1: second-layer content classifier
    "enable_bola_guard",     # Demo 1: object-level authorization on account access
    "enable_llm",            # Demo 1: live Gemini LLM planner vs deterministic planner
    "enable_egress_policy",  # Demo 2: per-destination egress allowlist (Agent Gateway style)
    "enable_agent_identity",  # Demo 3: require a valid agent identity on tool calls
)


@dataclass
class Guardrails:
    enable_model_armor: bool = False
    enable_dlp_redaction: bool = False
    enable_shieldgemma: bool = False
    enable_bola_guard: bool = False
    enable_llm: bool = False
    enable_egress_policy: bool = False
    enable_agent_identity: bool = False

    @classmethod
    def from_env(cls) -> "Guardrails":
        return cls(**{f: _bool(f.upper(), False) for f in GUARDRAIL_FLAGS})

    def merged(self, overrides: dict | None) -> "Guardrails":
        """Return a copy with any per-request overrides applied."""
        base = asdict(self)
        for key, value in (overrides or {}).items():
            if key in base and isinstance(value, bool):
                base[key] = value
        return Guardrails(**base)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Settings:
    # Vertex / Gemini Enterprise Agent Platform
    project_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    location: str = field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"))
    model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "gemini-3.5-flash"))
    use_llm: bool = field(default_factory=lambda: _bool("ENABLE_LLM", False))

    # Model Armor (optional live integration; heuristic fallback always available)
    model_armor_template: str = field(default_factory=lambda: os.getenv("MODEL_ARMOR_TEMPLATE", ""))
    shieldgemma_endpoint: str = field(default_factory=lambda: os.getenv("SHIELDGEMMA_ENDPOINT", "vertex-ai"))

    # Demo 2 — egress
    allowed_egress_hosts: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            h.strip()
            for h in os.getenv("ALLOWED_EGRESS_HOSTS", "finance.internal,api.atlas.demo").split(",")
            if h.strip()
        )
    )
    # example.com resolves and responds, so the *attack* path visibly REACHES it;
    # the "steal" path drives the exfiltration flag. Swap for a host you control if you like.
    exfil_canary_url: str = field(
        default_factory=lambda: os.getenv("EXFIL_CANARY_URL", "https://example.com/steal")
    )
    metadata_url: str = field(
        default_factory=lambda: os.getenv(
            "METADATA_URL",
            "http://metadata.google.internal/computeMetadata/v1/instance/"
            "service-accounts/default/token",
        )
    )

    # Demo 3 — the identity the finance tool-server trusts for the planner agent
    finance_trusted_identity: str = field(
        default_factory=lambda: os.getenv("FINANCE_TRUSTED_IDENTITY", "spiffe://atlas/planner")
    )

    guardrails: Guardrails = field(default_factory=Guardrails.from_env)


settings = Settings()
