"""Central configuration for AggreGuard middleware and evaluation.

Tunable knobs for the aggregation monitor (Component 4) live here so they can be swept
as ablation dimensions per the project plan (§4 / §9). This is the configuration the
system actually ships and that the evaluation uses — there is no separate hand-tuned
eval config (a red-team found that presenting eval-only numbers as system performance
overstated results).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AggregationConfig(BaseModel):
    """Parameters for the aggregation/inference monitor (Component 4)."""

    tau: float = Field(1.0, description="Cumulative sensitivity budget threshold S>=tau -> escalate.")
    k: int = Field(2, description="k-anonymity floor; escalate when 0 < anon_set < k.")

    # A disclosed fact stays disclosed: by default the cumulative budget does NOT decay
    # (decay would let a patient attacker defeat a slow leak by spacing it out). Decay can
    # be enabled for a 'recent activity' interpretation; half_life then applies.
    decay_enabled: bool = Field(False, description="Apply time decay to the sensitivity budget.")
    half_life_seconds: float = Field(86400.0, description="Decay half-life when decay_enabled.")

    # Per-attribute sensitivity weights w(a). Quasi-identifiers are low weight (their risk
    # is in *combination*, handled by the k-anon branch); direct-sensitive fields are high.
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            # quasi-identifiers (low individual weight)
            "zip": 0.2, "gender": 0.15, "birth_year": 0.2, "dob": 0.25, "age": 0.15, "city": 0.2,
            # directly sensitive (high weight)
            "ssn": 1.0, "ssn_last4": 0.5, "credit_card": 1.0, "medical_condition": 0.6,
            "salary": 0.5, "address": 0.5, "phone": 0.3, "email": 0.3, "name": 0.2,
            # routine / harmless
            "order_status": 0.1, "newsletter_optin": 0.05,
        }
    )
    quasi_identifiers: set[str] = Field(
        default_factory=lambda: {"zip", "gender", "birth_year", "dob", "age", "city"},
        description="Attributes whose *combination* enables re-identification (not direct ids).",
    )
    # Heuristic synonym canonicalization so trivial attribute renaming (postal_code->zip)
    # does not evade the QID match. NOT semantic — a known, documented limitation.
    attr_aliases: dict[str, str] = Field(
        default_factory=lambda: {
            "postal_code": "zip", "zipcode": "zip", "zip_code": "zip",
            "sex": "gender",
            "yob": "birth_year", "year_of_birth": "birth_year", "birthyear": "birth_year",
            "date_of_birth": "dob", "birthdate": "dob",
        }
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
