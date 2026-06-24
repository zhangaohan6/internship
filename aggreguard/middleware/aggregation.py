"""Component 4 ★ — aggregation / inference monitor (the project's core novelty).

Tracks cumulative information disclosure per (session × data-subject) and escalates when
a sequence of individually-benign disclosures either (a) crosses a cumulative
sensitivity budget ``tau`` or (b) collapses the data subject's anonymity set below ``k``
(k-anonymity / quasi-identifier re-identification). Prefers HITL escalation over hard
block to keep the false-positive rate low (plan §4 / §9).

Only disclosures flowing to an *untrusted* sink and linkable to an entity are scored;
internal reasoning reads are ignored, so normal multi-step processing of one subject
does not accumulate. Time decay prevents stale history from dominating.

This is what I/O text filters (Lakera, LLM Guard) and single-step injection detectors
structurally cannot see: each step here is individually benign.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aggreguard.config import AggregationConfig

# Decision outcomes.
ALLOW = "allow"
ESCALATE_HITL = "escalate_hitl"

# Sink that leaves the trust boundary (external send / write to attacker-controllable
# output). Disclosures to anything else are not scored.
UNTRUSTED_SINK = "untrusted"

# A reference population is a list of records mapping quasi-identifier -> value, used to
# estimate how many individuals are consistent with the QIDs disclosed about an entity.
Population = list[dict]


@dataclass
class DisclosureRecord:
    attr: str
    value: object
    weight: float
    timestamp: float  # epoch seconds; injected by caller (no wall-clock in core logic)
    sink_type: str = UNTRUSTED_SINK


@dataclass
class SubjectLedger:
    """Disclosure ledger for one (session, entity) pair."""

    records: list[DisclosureRecord] = field(default_factory=list)


@dataclass
class DisclosureDecision:
    decision: str                 # ALLOW | ESCALATE_HITL
    sensitivity: float            # cumulative S(entity) at this point
    anonymity_set: int | None     # estimated anon-set size, or None if no population
    reasons: list[str] = field(default_factory=list)

    @property
    def escalated(self) -> bool:
        return self.decision == ESCALATE_HITL


class AggregationMonitor:
    def __init__(self, config: AggregationConfig | None = None, population: Population | None = None):
        self.config = config or AggregationConfig()
        self.population = population
        # Columns the population actually carries (restrict QID matching to these).
        self._pop_cols = set(population[0].keys()) if population else set()
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
    ) -> DisclosureDecision:
        """Process one outbound disclosure; return a DisclosureDecision."""
        if sink_type != UNTRUSTED_SINK:  # only count outflow past the trust boundary
            return DisclosureDecision(ALLOW, 0.0, None, ["sink not untrusted; not scored"])

        ledger = self._disclosed.setdefault(session_id, {}).setdefault(entity, SubjectLedger())
        ledger.records.append(
            DisclosureRecord(attr=attr, value=value, weight=self._weight(attr),
                             timestamp=now, sink_type=sink_type)
        )

        s = self._cumulative_sensitivity(ledger, now)
        anon = self._estimate_anonymity_set(ledger)

        reasons: list[str] = []
        decision = ALLOW
        if s >= self.config.tau:
            decision = ESCALATE_HITL
            reasons.append(f"sensitivity budget S={s:.2f} >= tau={self.config.tau}")
        if anon is not None and anon < self.config.k:
            decision = ESCALATE_HITL
            reasons.append(f"anonymity set {anon} < k={self.config.k} (re-identifiable)")
        if not reasons:
            reasons.append(f"within budget (S={s:.2f} < tau, anon={anon})")

        return DisclosureDecision(decision, s, anon, reasons)

    def reset(self, session_id: str | None = None) -> None:
        """Clear ledgers — for one session or all (used between eval scenarios)."""
        if session_id is None:
            self._disclosed.clear()
        else:
            self._disclosed.pop(session_id, None)

    def _weight(self, attr: str) -> float:
        return self.config.weights.get(attr, 0.1)

    def _decay(self, dt: float) -> float:
        if dt <= 0:
            return 1.0
        return 0.5 ** (dt / self.config.half_life_seconds)

    def _cumulative_sensitivity(self, ledger: SubjectLedger, now: float) -> float:
        return sum(r.weight * self._decay(now - r.timestamp) for r in ledger.records)

    def _estimate_anonymity_set(self, ledger: SubjectLedger) -> int | None:
        """Number of reference-population members consistent with the disclosed QIDs.

        Returns None when no population is configured (k-anon branch disabled). Only
        quasi-identifiers that exist as population columns are used; the latest value
        wins if an attribute is disclosed more than once.
        """
        if not self.population:
            return None
        qid_values: dict[str, object] = {}
        for r in ledger.records:
            if r.attr in self.config.quasi_identifiers and r.attr in self._pop_cols:
                qid_values[r.attr] = r.value
        if not qid_values:
            return len(self.population)
        return sum(
            1 for person in self.population
            if all(str(person.get(a)) == str(v) for a, v in qid_values.items())
        )
