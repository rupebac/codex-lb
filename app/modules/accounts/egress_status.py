"""Computed egress status, fleet report, and load-balancer guardrail filtering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.core.config.settings import Settings
from app.db.models import Account
from app.modules.accounts.schemas import AccountEgressReportResponse, AccountEgressStatus

EgressPrimaryStatus = Literal["probe_failed", "shared_egress", "direct_egress", "ok", "unknown"]


@dataclass(frozen=True, slots=True)
class _EgressRow:
    account_id: str
    proxy_host: str | None
    proxy_remote_dns: bool
    egress_last_observed_ip: str | None
    egress_last_observed_at: datetime | None
    egress_last_checked_at: datetime | None
    egress_last_probe_status: str
    egress_last_probe_error: str | None


def _account_to_row(account: Account) -> _EgressRow:
    return _EgressRow(
        account_id=account.id,
        proxy_host=account.proxy_host,
        proxy_remote_dns=bool(account.proxy_remote_dns),
        egress_last_observed_ip=account.egress_last_observed_ip,
        egress_last_observed_at=account.egress_last_observed_at,
        egress_last_checked_at=account.egress_last_checked_at,
        egress_last_probe_status=account.egress_last_probe_status,
        egress_last_probe_error=account.egress_last_probe_error,
    )


def _is_report_eligible(row: _EgressRow) -> bool:
    return row.egress_last_probe_status == "ok" and row.egress_last_observed_ip is not None


def _has_configured_proxy(row: _EgressRow) -> bool:
    return row.proxy_host is not None


def _build_warnings(row: _EgressRow) -> list[str]:
    if _has_configured_proxy(row) and not row.proxy_remote_dns:
        return ["local_dns_risk"]
    return []


def _compute_primary_status(row: _EgressRow, *, shared_with: list[str]) -> EgressPrimaryStatus:
    if row.egress_last_probe_status == "probe_failed":
        return "probe_failed"
    if row.egress_last_probe_status == "ok" and row.egress_last_observed_ip is not None:
        if shared_with:
            return "shared_egress"
        if not _has_configured_proxy(row):
            return "direct_egress"
        return "ok"
    return "unknown"


def _inline_observed_ip(row: _EgressRow) -> str | None:
    if row.egress_last_probe_status != "ok":
        return None
    return row.egress_last_observed_ip


def build_account_egress_statuses(accounts: list[Account]) -> list[AccountEgressStatus]:
    rows = [_account_to_row(account) for account in accounts]
    ip_to_ids: dict[str, list[str]] = {}
    for row in rows:
        if not _is_report_eligible(row):
            continue
        ip = row.egress_last_observed_ip
        assert ip is not None
        ip_to_ids.setdefault(ip, []).append(row.account_id)

    statuses: list[AccountEgressStatus] = []
    for row in rows:
        shared_with: list[str] = []
        if _is_report_eligible(row):
            ip = row.egress_last_observed_ip
            assert ip is not None
            shared_with = [account_id for account_id in ip_to_ids.get(ip, []) if account_id != row.account_id]

        primary = _compute_primary_status(row, shared_with=shared_with)
        statuses.append(
            AccountEgressStatus(
                account_id=row.account_id,
                status=primary,
                observed_ip=_inline_observed_ip(row),
                checked_at=row.egress_last_checked_at or row.egress_last_observed_at,
                error=row.egress_last_probe_error if row.egress_last_probe_status == "probe_failed" else None,
                configured_proxy=_has_configured_proxy(row),
                proxy_remote_dns=row.proxy_remote_dns if _has_configured_proxy(row) else None,
                shared_with_account_ids=shared_with,
                warnings=_build_warnings(row),
            )
        )
    return statuses


def build_account_egress_report(accounts: list[Account]) -> AccountEgressReportResponse:
    account_statuses = build_account_egress_statuses(accounts)
    return AccountEgressReportResponse(
        accounts=account_statuses,
        unknown_count=sum(1 for entry in account_statuses if entry.status == "unknown"),
        failed_count=sum(1 for entry in account_statuses if entry.status == "probe_failed"),
        direct_count=sum(1 for entry in account_statuses if entry.status == "direct_egress"),
        shared_ip_count=sum(1 for entry in account_statuses if entry.status == "shared_egress"),
    )


def egress_status_by_account_id(accounts: list[Account]) -> dict[str, AccountEgressStatus]:
    return {entry.account_id: entry for entry in build_account_egress_statuses(accounts)}


def filter_accounts_for_egress_guardrails(
    selectable_accounts: list[Account],
    settings: Settings,
) -> list[Account]:
    if settings.account_egress_guardrail_mode != "block":
        return selectable_accounts

    selectable_ip_counts: dict[str, int] = {}
    for account in selectable_accounts:
        if account.egress_last_probe_status == "ok" and account.egress_last_observed_ip:
            ip = account.egress_last_observed_ip
            selectable_ip_counts[ip] = selectable_ip_counts.get(ip, 0) + 1

    filtered: list[Account] = []
    for account in selectable_accounts:
        is_confirmed_direct = (
            account.egress_last_probe_status == "ok"
            and account.egress_last_observed_ip is not None
            and account.proxy_host is None
        )
        if is_confirmed_direct and not settings.account_egress_allow_direct_accounts:
            continue
        if not settings.account_egress_allow_shared_observed_ip:
            ip = account.egress_last_observed_ip
            if account.egress_last_probe_status == "ok" and ip is not None and selectable_ip_counts.get(ip, 0) > 1:
                continue
        filtered.append(account)
    return filtered
