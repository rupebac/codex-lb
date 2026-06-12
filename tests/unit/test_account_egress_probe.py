"""Unit tests for account egress IP probe parsing and execution."""

from __future__ import annotations

import pytest

from app.core.clients import account_egress_probe as egress_probe_module
from app.core.clients.account_egress_probe import parse_observed_ip, probe_account_egress_ip

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('{"ip":"93.184.216.34"}', "93.184.216.34"),
        ("8.8.8.8", "8.8.8.8"),
        ("  1.1.1.1\n", "1.1.1.1"),
    ],
)
def test_parse_observed_ip_accepts_global_addresses(body: str, expected: str) -> None:
    assert parse_observed_ip(body) == expected


@pytest.mark.parametrize(
    "body",
    [
        '{"ip":"203.0.113.10"}',
        '{"ip":"10.0.0.1"}',
        '{"ip":"127.0.0.1"}',
        "",
        "not-an-ip",
        '{"address":"8.8.8.8"}',
    ],
)
def test_parse_observed_ip_rejects_invalid_or_non_global(body: str) -> None:
    assert parse_observed_ip(body) is None


@pytest.mark.asyncio
async def test_probe_account_egress_ip_uses_injected_http_get() -> None:
    captured: dict[str, str] = {}

    async def _stub(account_id: str, probe_url: str, timeout_seconds: float) -> tuple[int, str]:
        captured["account_id"] = account_id
        captured["probe_url"] = probe_url
        captured["timeout_seconds"] = str(timeout_seconds)
        return 200, '{"ip":"93.184.216.34"}'

    egress_probe_module._set_http_get_for_test(_stub)
    try:
        result = await probe_account_egress_ip("acc_probe")
    finally:
        egress_probe_module._set_http_get_for_test(None)

    assert captured["account_id"] == "acc_probe"
    assert result.ok is True
    assert result.observed_ip == "93.184.216.34"
    assert result.checked_at is not None


@pytest.mark.asyncio
async def test_probe_account_egress_ip_classifies_http_errors() -> None:
    async def _stub(account_id: str, probe_url: str, timeout_seconds: float) -> tuple[int, str]:
        return 503, "unavailable"

    egress_probe_module._set_http_get_for_test(_stub)
    try:
        result = await probe_account_egress_ip("acc_probe")
    finally:
        egress_probe_module._set_http_get_for_test(None)

    assert result.ok is False
    assert result.error == "probe_http_503"
