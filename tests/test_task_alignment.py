"""Tests for Component 3 — task-alignment monitor."""

from aggreguard.middleware.task_alignment import (
    Alignment,
    TaskAlignmentMonitor,
    UserIntent,
    is_aligned,
)


def test_read_only_intent_blocks_exfiltration():
    intent = UserIntent(description="summarize my emails", read_only=True)
    mon = TaskAlignmentMonitor(intent)
    assert mon.check({"tool": "read_email", "args": {}}) == Alignment.ALIGNED
    assert mon.check({"tool": "send_email", "args": {}}) == Alignment.MISALIGNED


def test_allowlist_blocks_unlisted_tool():
    intent = UserIntent(description="book a flight", allowed_tools={"search_flights", "book_flight"})
    mon = TaskAlignmentMonitor(intent)
    assert mon.check({"tool": "book_flight", "args": {}}) == Alignment.ALIGNED
    assert mon.check({"tool": "transfer", "args": {}}) == Alignment.MISALIGNED


def test_judge_hook_overrides_rules():
    intent = UserIntent(description="anything", read_only=True)
    # Judge force-aligns even an exfil tool (e.g. user explicitly confirmed).
    mon = TaskAlignmentMonitor(intent, judge=lambda i, a: Alignment.ALIGNED)
    assert mon.check({"tool": "send_email"}) == Alignment.ALIGNED

    # Judge that defers (returns None) falls back to rules -> misaligned.
    mon2 = TaskAlignmentMonitor(intent, judge=lambda i, a: None)
    assert mon2.check({"tool": "send_email"}) == Alignment.MISALIGNED


def test_is_aligned_convenience():
    intent = UserIntent(description="read stuff", read_only=True)
    assert is_aligned(intent, {"tool": "read_email"}) is True
    assert is_aligned(intent, {"tool": "delete"}) is False
