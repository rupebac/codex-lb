"""Unit tests for computed egress status and guardrail filtering."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config.settings import Settings
from app.db.models import Account, AccountStatus
from app.modules.accounts.egress_status import (
    build_account_egress_report,
    build_account_egress_statuses,
    filter_accounts_for_egress_guardrails,
)

pytestmark = pytest.mark.unit


def _account(
    account_id: str,
    *,
    status: AccountStatus = AccountStatus.ACTIVE,
    proxy_host: str | None = None,
    proxy_remote_dns: bool = True,
    observed_ip: str | None = None,
    probe_status: str = "unknown",
    probe_error: str | None = None,
) -> Account:
    checked_at = datetime(2026, 6, 12, tzinfo=timezone.utc) if observed_ip else None
    return Account(
        id=account_id,
        email=f"{account_id}@example.com",
        plan_type="plus",
        access_token_encrypted=b"a",
        refresh_token_encrypted=b"r",
        id_token_encrypted=b"i",
        last_refresh=checked_at,
        status=status,
        proxy_host=proxy_host,
        proxy_port=1080 if proxy_host else None,
        proxy_remote_dns=proxy_remote_dns,
        egress_last_observed_ip=observed_ip,
        egress_last_observed_at=checked_at,
        egress_last_checked_at=checked_at,
        egress_last_probe_status=probe_status,
        egress_last_probe_error=probe_error,
    )


def test_shared_egress_takes_precedence_over_direct_egress() -> None:
    accounts = [
        _account("a", observed_ip="93.184.216.34", probe_status="ok"),
        _account("b", observed_ip="93.184.216.34", probe_status="ok"),
    ]
    statuses = build_account_egress_statuses(accounts)
    by_id = {entry.account_id: entry for entry in statuses}
    assert by_id["a"].status == "shared_egress"
    assert by_id["b"].status == "shared_egress"
    assert by_id["a"].shared_with_account_ids == ["b"]


def test_local_dns_risk_is_warning_only() -> None:
    account = _account(
        "proxy",
        proxy_host="proxy.example.com",
        proxy_remote_dns=False,
        observed_ip="8.8.8.8",
        probe_status="ok",
    )
    status = build_account_egress_statuses([account])[0]
    assert status.status == "ok"
    assert status.warnings == ["local_dns_risk"]


def test_failed_probe_does_not_expose_observed_ip() -> None:
    account = _account(
        "failed",
        observed_ip=None,
        probe_status="probe_failed",
        probe_error="invalid_or_non_global_ip",
    )
    status = build_account_egress_statuses([account])[0]
    assert status.status == "probe_failed"
    assert status.observed_ip is None
    assert status.error == "invalid_or_non_global_ip"


def test_fleet_report_summary_counts() -> None:
    accounts = [
        _account("u1"),
        _account("u2"),
        _account("f1", probe_status="probe_failed", probe_error="timeout"),
        _account("d1", observed_ip="1.2.3.4", probe_status="ok"),
        _account("s1", observed_ip="5.6.7.8", probe_status="ok"),
        _account("s2", observed_ip="5.6.7.8", probe_status="ok"),
    ]
    report = build_account_egress_report(accounts)
    assert len(report.accounts) == 6
    assert report.unknown_count == 2
    assert report.failed_count == 1
    assert report.direct_count == 1
    assert report.shared_ip_count == 2


def test_block_mode_removes_direct_egress_accounts() -> None:
    accounts = [
        _account("direct", observed_ip="1.2.3.4", probe_status="ok"),
        _account("unknown"),
    ]
    settings = Settings(account_egress_guardrail_mode="block")
    filtered = filter_accounts_for_egress_guardrails(accounts, settings)
    assert [account.id for account in filtered] == ["unknown"]


def test_proxied_account_is_not_blocked_by_unique_selectable_ip() -> None:
    active = _account(
        "active",
        proxy_host="proxy.example.com",
        observed_ip="9.9.9.9",
        probe_status="ok",
    )
    settings = Settings(account_egress_guardrail_mode="block")
    filtered = filter_accounts_for_egress_guardrails([active], settings)
    assert [account.id for account in filtered] == ["active"]


def test_selectable_shared_ip_is_blocked_in_block_mode() -> None:
    a = _account("a", observed_ip="9.9.9.9", probe_status="ok")
    b = _account("b", observed_ip="9.9.9.9", probe_status="ok")
    settings = Settings(account_egress_guardrail_mode="block")
    filtered = filter_accounts_for_egress_guardrails([a, b], settings)
    assert filtered == []


def test_direct_egress_blocks_even_when_non_selectable_peer_shares_ip() -> None:
    active = _account("active", observed_ip="9.9.9.9", probe_status="ok")
    settings = Settings(account_egress_guardrail_mode="block")
    filtered = filter_accounts_for_egress_guardrails([active], settings)
    assert filtered == []
