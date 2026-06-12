from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app.core.auth.token_refresh_scheduler import (
    BackgroundTokenRefreshPacer,
    TokenRefreshSource,
    compute_failure_backoff_at,
    compute_initial_next_allowed_at,
    evaluate_refresh_decision,
    is_past_hard_max_refresh,
    reset_background_token_refresh_pacer,
    set_background_pacer_override,
    set_scheduler_monotonic_override,
    set_scheduler_now_override,
)
from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_scheduler_overrides() -> None:
    set_scheduler_now_override(None)
    set_scheduler_monotonic_override(None)
    set_background_pacer_override(None)
    reset_background_token_refresh_pacer()


def _account(account_id: str, *, status: AccountStatus = AccountStatus.ACTIVE) -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access"),
        refresh_token_encrypted=encryptor.encrypt("refresh"),
        id_token_encrypted=encryptor.encrypt("id"),
        last_refresh=utcnow().replace(year=utcnow().year - 1),
        status=status,
        deactivation_reason=None,
        token_refresh_failure_count=0,
    )


def test_compute_initial_next_allowed_at_spreads_accounts() -> None:
    now = utcnow()
    a = compute_initial_next_allowed_at("acc_one", now=now)
    b = compute_initial_next_allowed_at("acc_two", now=now)
    assert a >= now
    assert b >= now
    assert a != b or "acc_one" == "acc_two"


def test_null_schedule_initialization_defers_background_refresh() -> None:
    now = utcnow()
    account = _account("acc_init")
    account.last_refresh = now - timedelta(days=1)
    decision = evaluate_refresh_decision(
        account,
        source=TokenRefreshSource.USAGE_REFRESH_401,
        force=True,
        now=now,
    )
    assert decision.allowed is False
    assert decision.reason == "scheduled"
    assert decision.initialized_schedule is True
    assert decision.next_allowed_at is not None
    assert decision.next_allowed_at > now


def test_background_skips_quota_exceeded_when_disabled(monkeypatch) -> None:
    from types import SimpleNamespace

    from app.core.auth import token_refresh_scheduler as scheduler_module

    monkeypatch.setattr(
        scheduler_module,
        "get_settings",
        lambda: SimpleNamespace(account_token_refresh_background_refresh_quota_exceeded=False),
    )
    account = _account("acc_quota", status=AccountStatus.QUOTA_EXCEEDED)
    decision = evaluate_refresh_decision(account, source=TokenRefreshSource.WARMUP, force=True)
    assert decision.allowed is False
    assert decision.reason == "skipped_quota"


def test_failure_backoff_increases_with_count() -> None:
    now = utcnow()
    first = compute_failure_backoff_at(1, "acc_backoff", now=now)
    second = compute_failure_backoff_at(2, "acc_backoff", now=now)
    assert first > now
    assert second > first


def test_is_past_hard_max_refresh() -> None:
    now = utcnow()
    recent = now - timedelta(days=1)
    stale = now - timedelta(days=30)
    assert is_past_hard_max_refresh(recent, now=now) is False
    assert is_past_hard_max_refresh(stale, now=now) is True


@pytest.mark.asyncio
async def test_background_pacer_enforces_concurrency_and_spacing(monkeypatch) -> None:
    pacer = BackgroundTokenRefreshPacer(concurrency=1, min_start_spacing_seconds=0.05)
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    lease1 = await pacer.acquire()
    lease2_task = asyncio.create_task(pacer.acquire())
    await asyncio.sleep(0)
    assert not lease2_task.done()
    lease1.release()
    lease2 = await lease2_task
    lease2.release()
    assert sleeps


@pytest.mark.asyncio
async def test_background_pacer_spaces_three_starts(monkeypatch) -> None:
    from app.core.auth import token_refresh_scheduler as scheduler_module

    clock = [0.0]

    monkeypatch.setattr(scheduler_module, "_monotonic_now", lambda: clock[0])

    real_sleep = asyncio.sleep

    async def fake_sleep(seconds: float) -> None:
        clock[0] += seconds
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    pacer = BackgroundTokenRefreshPacer(concurrency=1, min_start_spacing_seconds=300.0)
    starts: list[float] = []

    for account_id in ("a", "b", "c"):
        lease = await pacer.acquire()
        starts.append(clock[0])
        lease.release()

    assert starts == [0.0, 300.0, 600.0]


@pytest.mark.asyncio
async def test_background_pacer_releases_permit_when_cancelled_while_waiting_for_lock() -> None:
    pacer = BackgroundTokenRefreshPacer(concurrency=1, min_start_spacing_seconds=0.0)
    await pacer._lock.acquire()
    task = asyncio.create_task(pacer.acquire())
    await asyncio.sleep(0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    pacer._lock.release()

    lease = await asyncio.wait_for(pacer.acquire(), timeout=0.1)
    lease.release()


def test_build_skip_schedule_update_records_source_as_last_reason() -> None:
    from app.core.auth.token_refresh_scheduler import build_skip_schedule_update

    now = utcnow()
    update = build_skip_schedule_update(
        source=TokenRefreshSource.WARMUP,
        reason="skipped_quota",
        attempt_at=now,
        next_allowed_at=now,
        initialized_schedule=False,
    )
    assert update is not None
    assert update.last_result == "skipped"
    assert update.last_reason == "warmup"


def test_next_refresh_eligible_at_matches_should_refresh_boundary() -> None:
    from app.core.auth.refresh import next_refresh_eligible_at, should_refresh

    now = utcnow()
    last_refresh = now - timedelta(days=9)
    account_id = "acc_boundary"
    eligible_at = next_refresh_eligible_at(last_refresh, account_id=account_id)
    assert should_refresh(last_refresh, eligible_at + timedelta(seconds=1), account_id=account_id) is True
    assert should_refresh(last_refresh, eligible_at, account_id=account_id) is False


@pytest.mark.asyncio
async def test_background_pacer_concurrent_acquires_do_not_deadlock(monkeypatch) -> None:
    from app.core.auth import token_refresh_scheduler as scheduler_module

    clock = [0.0]
    monkeypatch.setattr(scheduler_module, "_monotonic_now", lambda: clock[0])

    real_sleep = asyncio.sleep

    async def fake_sleep(seconds: float) -> None:
        clock[0] += seconds
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    pacer = BackgroundTokenRefreshPacer(concurrency=1, min_start_spacing_seconds=300.0)

    async def run_refresh() -> None:
        lease = await pacer.acquire()
        lease.release()

    await asyncio.wait_for(asyncio.gather(*(run_refresh() for _ in range(3))), timeout=2.0)
