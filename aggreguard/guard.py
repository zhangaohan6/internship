"""AggreGuard composition layer.

Strings the middleware components into a single, framework-agnostic decision over one
agent *step* (a proposed tool call together with the provenance of its arguments and
any untrusted text it would consume). Severity ordering: BLOCK > ESCALATE_HITL > ALLOW.

Pipeline per step:
  C2 injection detection on untrusted inputs ─┐
  C1 trust-boundary violation                 │
  C3 task-alignment check                     ├─► combine (most severe wins) ─► C6 log
  C5 high-risk action gating                  │
  C4 aggregation/inference monitor            ─┘

Unlike C1/C2/C3/C5 (stateless per-step checks), C4 is *stateful*: the AggreGuard instance
holds one AggregationMonitor across a session, and each step feeds it the disclosures the
tool call would make (entity, attribute, value, sink). This is the seam that
``integrations/`` adapt onto a concrete agent framework. It holds no framework imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from aggreguard.config import GuardConfig
from aggreguard.middleware.action_gate import GateDecision, gate
from aggreguard.middleware.aggregation import AggregationMonitor
from aggreguard.middleware.injection_detect import InjectionDetector, KeywordInjectionDetector
from aggreguard.middleware.logging import DecisionLog, DecisionLogger
from aggreguard.middleware.provenance import Tagged, trust_violation
from aggreguard.middleware.task_alignment import Alignment, TaskAlignmentMonitor, UserIntent


class GuardDecision(IntEnum):
    """Severity-ordered so we can max() across components."""

    ALLOW = 0
    ESCALATE_HITL = 1
    BLOCK = 2


_GATE_TO_GUARD = {
    GateDecision.ALLOW: GuardDecision.ALLOW,
    GateDecision.ESCALATE_HITL: GuardDecision.ESCALATE_HITL,
    GateDecision.BLOCK: GuardDecision.BLOCK,
}


@dataclass
class Finding:
    component: str
    decision: GuardDecision
    reason: str


@dataclass
class GuardResult:
    decision: GuardDecision
    findings: list[Finding] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.decision == GuardDecision.ALLOW

    @property
    def reasons(self) -> list[str]:
        return [f"{f.component}: {f.reason}" for f in self.findings]


@dataclass
class Disclosure:
    """One piece of data a tool call would reveal about a subject (for C4)."""

    entity: str
    attr: str
    value: object
    sink_type: str = "untrusted"  # "untrusted" (leaves trust boundary) | "internal"


@dataclass
class GuardStep:
    """One step to adjudicate."""

    tool: str
    args: dict = field(default_factory=dict)
    arg_provenance: list[Tagged] = field(default_factory=list)
    untrusted_texts: list[str] = field(default_factory=list)
    disclosures: list[Disclosure] = field(default_factory=list)
    session_id: str | None = None
    now: float = 0.0  # epoch seconds injected by the caller


class AggreGuard:
    """Composes the middleware components into one per-step decision."""

    def __init__(
        self,
        intent: UserIntent | None = None,
        config: GuardConfig | None = None,
        injection_detector: InjectionDetector | None = None,
        logger: DecisionLogger | None = None,
        population: list[dict] | None = None,
        enabled: set[str] | None = None,
    ):
        self.config = config or GuardConfig()
        self.intent = intent
        self.injection_detector = injection_detector or KeywordInjectionDetector()
        self.logger = logger or DecisionLogger()
        self._aligner = TaskAlignmentMonitor(intent) if intent is not None else None
        # C4 is stateful across the session — one monitor per AggreGuard instance.
        self.aggregation = AggregationMonitor(self.config.aggregation, population=population)
        # Component ablation switch: which findings count toward the decision. None = all.
        # Names: "injection_detect", "provenance", "task_alignment", "action_gate", "aggregation".
        self.enabled = enabled

    def evaluate(self, step: GuardStep) -> GuardResult:
        findings: list[Finding] = []

        # C2 — injection in untrusted inputs. Treat as escalate (don't hard-block on a
        # baseline detector's say-so; favors low FPR per plan §9).
        for text in step.untrusted_texts:
            score = self.injection_detector.detect(text)
            if score >= 0.5:
                findings.append(Finding("injection_detect",
                                        GuardDecision.ESCALATE_HITL,
                                        f"injection score {score:.2f}"))
                break

        # C1 — trust boundary: untrusted data driving a high-risk tool is a hard breach.
        if trust_violation(step.tool, step.arg_provenance, self.config.high_risk_tools):
            findings.append(Finding("provenance",
                                    GuardDecision.BLOCK,
                                    f"high-risk tool {step.tool!r} driven by untrusted data"))

        # C3 — task alignment.
        if self._aligner is not None:
            verdict = self._aligner.check({"tool": step.tool, "args": step.args})
            if verdict == Alignment.MISALIGNED:
                findings.append(Finding("task_alignment",
                                        GuardDecision.ESCALATE_HITL,
                                        f"action {step.tool!r} deviates from intent"))

        # C5 — high-risk action gating per policy mode.
        gate_decision = gate(step.tool, self.config)
        if gate_decision != GateDecision.ALLOW:
            findings.append(Finding("action_gate",
                                    _GATE_TO_GUARD[gate_decision],
                                    f"high-risk tool {step.tool!r} (mode={self.config.action_gate_mode})"))

        # C4 — aggregation/inference monitor (stateful). Feed each disclosure this step
        # would make; escalate if cumulative disclosure crosses budget or re-identifies.
        for d in step.disclosures:
            agg = self.aggregation.on_disclosure(
                session_id=step.session_id or "default", entity=d.entity, attr=d.attr,
                value=d.value, sink_type=d.sink_type, now=step.now,
            )
            if agg.escalated:
                findings.append(Finding("aggregation", GuardDecision.ESCALATE_HITL,
                                        f"subject {d.entity!r}: {'; '.join(agg.reasons)}"))
                break

        # Component ablation: keep only findings from enabled components.
        if self.enabled is not None:
            findings = [f for f in findings if f.component in self.enabled]

        decision = max((f.decision for f in findings), default=GuardDecision.ALLOW)

        # C6 — log the final decision and each contributing finding.
        self.logger.log_decision(DecisionLog(
            action=step.tool,
            component="aggreguard",
            decision=decision.name.lower(),
            reason="; ".join(f"{f.component}:{f.reason}" for f in findings) or "no findings",
            session_id=step.session_id,
            timestamp=step.now,
        ))

        return GuardResult(decision=decision, findings=findings)
