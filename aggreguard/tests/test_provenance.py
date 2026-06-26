"""Tests for Component 1 — provenance / trust boundaries."""

from aggreguard.middleware.provenance import (
    TrustLevel,
    combine_levels,
    derive,
    is_untrusted,
    tag,
    trust_violation,
)

HIGH_RISK = {"send_email", "transfer", "external_post", "delete"}


def test_taint_propagation_least_trusted_wins():
    assert combine_levels([TrustLevel.USER, TrustLevel.WEB]) == TrustLevel.WEB
    assert combine_levels([TrustLevel.USER, TrustLevel.TOOL]) == TrustLevel.TOOL
    assert combine_levels([]) == TrustLevel.USER  # no inputs => no taint


def test_derive_carries_lowest_trust_and_parents():
    user = tag("subject", TrustLevel.USER, source="user_msg")
    web = tag("click here", TrustLevel.WEB, source="web:evil.com")
    out = derive("subject + click here", [user, web], source="composed")
    assert out.level == TrustLevel.WEB
    assert is_untrusted(out)
    assert "web:evil.com" in out.parents


def test_high_risk_tool_from_untrusted_is_a_violation():
    web = tag("attacker@evil.com", TrustLevel.WEB, source="email_body")
    assert trust_violation("send_email", [web], HIGH_RISK) is True


def test_high_risk_tool_from_user_is_fine():
    user = tag("boss@corp.com", TrustLevel.USER, source="user_msg")
    assert trust_violation("send_email", [user], HIGH_RISK) is False


def test_low_risk_tool_never_violates():
    web = tag("anything", TrustLevel.WEB)
    assert trust_violation("read_email", [web], HIGH_RISK) is False
