"""Component 6 — decision logging / observability.

Emits a structured trace record for every allow / block / escalate decision
(action, hit component, decision, reason, confidence). Records go to an in-memory
buffer plus an optional JSONL sink; Langfuse export is wired when enabled.

Plan ref: §4 Component 6. Langfuse stays optional so the core has no heavy dep.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class DecisionLog:
    action: str
    component: str       # which middleware component fired (e.g. "action_gate")
    decision: str        # allow | block | escalate_hitl
    reason: str
    confidence: float = 1.0
    session_id: str | None = None
    timestamp: float | None = None  # epoch seconds; injected by caller, no wall-clock here

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass
class DecisionLogger:
    """Collects decision records; optionally mirrors them to a JSONL file / Langfuse."""

    jsonl_path: Path | None = None
    langfuse_enabled: bool = False
    records: list[DecisionLog] = field(default_factory=list)
    _langfuse: object | None = field(default=None, repr=False)

    def __post_init__(self):
        if self.langfuse_enabled:
            try:
                from langfuse import Langfuse  # imported lazily; optional dep

                self._langfuse = Langfuse()
            except Exception:
                # Observability must never break the guardrail path.
                self._langfuse = None

    def log_decision(self, record: DecisionLog) -> None:
        self.records.append(record)
        if self.jsonl_path is not None:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(record.to_json() + "\n")
        if self._langfuse is not None:
            try:
                self._langfuse.event(name=record.component, metadata=asdict(record))
            except Exception:
                pass  # best-effort export

    def __len__(self) -> int:
        return len(self.records)
