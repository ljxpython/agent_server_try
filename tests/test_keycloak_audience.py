from __future__ import annotations

from app.auth.audience import audience_matches


def test_audience_matches_string_aud() -> None:
    payload = {"aud": "agent-proxy"}
    assert audience_matches(payload, "agent-proxy") is True


def test_audience_matches_list_aud() -> None:
    payload = {"aud": ["account", "agent-proxy"]}
    assert audience_matches(payload, "agent-proxy") is True


def test_audience_matches_azp_when_aud_is_account() -> None:
    payload = {"aud": "account", "azp": "agent-proxy"}
    assert audience_matches(payload, "agent-proxy") is True


def test_audience_mismatch_returns_false() -> None:
    payload = {"aud": "account", "azp": "other-client"}
    assert audience_matches(payload, "agent-proxy") is False
