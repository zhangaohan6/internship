"""Component 4 ★ — aggregation / inference monitor (the project's core novelty).

Tracks cumulative information disclosure per (session × data-subject) and escalates
when a sequence of individually-benign disclosures crosses a sensitivity budget (tau)
or collapses an anonymity set below k. Prefers HITL escalation over hard block to keep
the false-positive rate low.

Plan ref: §4 Component 4. Status: SKELETON with algorithm scaffold (flesh out in Phase 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aggreguard.config import AggregationConfig

# Decision outcomes.
ALLOW = "allow"
ESCALATE_HITL = "escalate_hitl"


@dataclass
class DisclosureRecord:
    attr: str
    value: object
    weight: float
    timestamp: float  # epoch seconds; injected by caller (no wall-clock in core logic)


@dataclass
class SubjectLedger:
    """Disclosure ledger for one (session, entity) pair."""

    records: list[DisclosureRecord] = field(default_factory=list)


class AggregationMonitor:
    def __init__(self, config: AggregationConfig | None = None):
        self.config = config or AggregationConfig()
        # disclosed[session_id][entity] -> SubjectLedger
        self._disclosed: dict[str, dict[str, SubjectLedger]] = {}

    def on_disclosure(
        self,
        *,
        session_id: str,
        entity: str,
        attr: str,
        value: object,
        sink_type: str,
        now: float,
    ) -> str:
        """Process one outbound disclosure; return ALLOW or ESCALATE_HITL.

        Only disclosures flowing to an untrusted sink and linkable to an entity are
        scored — internal reasoning reads are ignored to avoid false positives.
        """
        if sink_type != "untrusted":  # only count outflow
            return ALLOW

        ledger = self._disclosed.setdefault(session_id, {}).setdefault(entity, SubjectLedger())
        ledger.records.append(
            DisclosureRecord(attr=attr, value=value, weight=self._weight(attr), timestamp=now)
        )

        s = self._cumulative_sensitivity(ledger, now)
        qids = {r.attr for r in ledger.records if r.attr in self.config.quasi_identifiers}
        anon = self._estimate_anonymity_set(entity, qids)

        if s >= self.config.tau or anon < self.config.k:
            return ESCALATE_HITL
        return ALLOW

    def _weight(self, attr: str) -> float:
        return self.config.weights.get(attr, 0.1)

    def _decay(self, dt: float) -> float:
        # Exponential decay with configured half-life; TODO(Phase 2): validate on dev set.
        if dt <= 0:
            return 1.0
        return 0.5 ** (dt / self.config.half_life_seconds)

    def _cumulative_sensitivity(self, ledger: SubjectLedger, now: float) -> float:
        return sum(r.weight * self._decay(now - r.timestamp) for r in ledger.records)

    def _estimate_anonymity_set(self, entity: str, qids: set[str]) -> int:
        # TODO(Phase 2): real k-anonymity estimate. Placeholder returns a large set
        # so the QID branch never fires until implemented.
        return 10**9
