"""Central configuration for AggreGuard middleware and evaluation.

Tunable knobs for the aggregation monitor (Component 4) live here so they can be
swept as ablation dimensions per the project plan (§4 / §9).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AggregationConfig(BaseModel):
    """Parameters for the aggregation/inference monitor (Component 4)."""

    tau: float = Field(1.0, description="Cumulative sensitivity budget threshold S>=tau -> escalate.")
    k: int = Field(5, description="k-anonymity floor; anon_set < k -> escalate.")
    half_life_seconds: float = Field(3600.0, description="Decay half-life for disclosed records.")
    # Per-attribute sensitivity weights w(a). Extend as the attribute taxonomy grows.
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "ssn": 1.0,
            "credit_card": 1.0,
            "dob": 0.5,
            "zip": 0.3,
            "gender": 0.2,
            "name": 0.4,
            "email": 0.4,
        }
    )
    quasi_identifiers: set[str] = Field(
        default_factory=lambda: {"zip", "dob", "gender", "name"},
        description="Attributes treated as quasi-identifiers for re-identification checks.",
    )


class GuardConfig(BaseModel):
    """Top-level guardrail configuration."""

    # Policy mode for high-risk action gating (Component 5): log | soft | hard.
    action_gate_mode: str = "soft"
    high_risk_tools: set[str] = Field(
        default_factory=lambda: {"send_email", "transfer", "external_post", "delete"}
    )
    aggregation: AggregationConfig = Field(default_factory=AggregationConfig)
    # Observability (Component 6).
    langfuse_enabled: bool = False


DEFAULT_CONFIG = GuardConfig()
