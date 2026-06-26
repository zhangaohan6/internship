"""Tests for Component 5 (action gating) and Component 6 (decision logging)."""

from aggreguard.config import GuardConfig
from aggreguard.middleware.action_gate import GateDecision, gate, is_high_risk
from aggreguard.middleware.logging import DecisionLog, DecisionLogger


def test_low_risk_tool_always_allowed():
    cfg = GuardConfig(action_gate_mode="hard")
    assert gate("read_email", cfg) == GateDecision.ALLOW


def test_high_risk_modes():
    assert gate("send_email", GuardConfig(action_gate_mode="log")) == GateDecision.ALLOW
    assert gate("send_email", GuardConfig(action_gate_mode="soft")) == GateDecision.ESCALATE_HITL
    assert gate("transfer", GuardConfig(action_gate_mode="hard")) == GateDecision.BLOCK
    assert is_high_risk("delete", GuardConfig())


def test_logger_buffers_and_writes_jsonl(tmp_path):
    path = tmp_path / "decisions.jsonl"
    logger = DecisionLogger(jsonl_path=path)
    logger.log_decision(DecisionLog(
        action="send_email", component="action_gate", decision="escalate_hitl",
        reason="high-risk tool", confidence=1.0, session_id="s1", timestamp=0.0,
    ))
    assert len(logger) == 1
    assert path.exists()
    assert "escalate_hitl" in path.read_text(encoding="utf-8")
