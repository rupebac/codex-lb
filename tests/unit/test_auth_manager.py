from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest

from app.core.auth.refresh import RefreshError, TokenRefreshResult, refresh_jitter_offset_seconds
from app.core.auth.token_refresh_scheduler import (
    BackgroundTokenRefreshPacer,
    TokenRefreshDeferred,
    TokenRefreshSource,
    reset_background_token_refresh_pacer,
    set_background_pacer_override,
    set_scheduler_monotonic_override,
    set_scheduler_now_override,
)
from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus
from app.modules.accounts import auth_manager as auth_manager_module
from app.modules.accounts.auth_manager import AccountsRepositoryPort, AuthManager

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_refresh_state() -> None:
    auth_manager_module._clear_refresh_singleflight_state()


class _DummyRepo:
    def __init__(self) -> None:
        self.tokens_payload: dict[str, object] | None = None
        self.status_payload: dict[str, object] | None = None
        self.schedule_payload: dict[str, object] | None = None
        self.schedule_only_calls = 0
        self.accounts_by_id: dict[str, Account] = {}

    async def get_by_id(self, account_id: str) -> Account | None:
        return self.accounts_by_id.get(account_id)

    async def update_status(
        self,
        account_id: str,
        status: AccountStatus,
        deactivation_reason: str | None = None,
        reset_at: int | None = None,
        blocked_at: int | None = None,
    ) -> bool:
        self.status_payload = {
            "account_id": account_id,
            "status": status,
            "deactivation_reason": deactivation_reason,
        }
        return True

    async def update_tokens(
        self,
        account_id: str,
        access_token_encrypted: bytes,
        refresh_token_encrypted: bytes,
        id_token_encrypted: bytes,
        last_refresh: datetime,
        plan_type: str | None = None,
        email: str | None = None,
        chatgpt_account_id: str | None = None,
        token_refresh_schedule: object = None,
    ) -> bool:
        from app.core.auth.token_refresh_scheduler import TokenRefreshScheduleUpdate, schedule_update_to_db_values

        self.tokens_payload = {
            "account_id": account_id,
            "access_token_encrypted": access_token_encrypted,
            "refresh_token_encrypted": refresh_token_encrypted,
            "id_token_encrypted": id_token_encrypted,
            "last_refresh": last_refresh,
            "plan_type": plan_type,
            "email": email,
            "chatgpt_account_id": chatgpt_account_id,
            "token_refresh_schedule": token_refresh_schedule,
        }
        if isinstance(token_refresh_schedule, TokenRefreshScheduleUpdate):
            self.schedule_payload = {
                "account_id": account_id,
                **schedule_update_to_db_values(token_refresh_schedule),
            }
        return True

    async def update_token_refresh_schedule(self, account_id: str, schedule: object) -> bool:
        from app.core.auth.token_refresh_scheduler import TokenRefreshScheduleUpdate, schedule_update_to_db_values

        self.schedule_only_calls += 1
        if isinstance(schedule, TokenRefreshScheduleUpdate):
            self.schedule_payload = {
                "account_id": account_id,
                **schedule_update_to_db_values(schedule),
            }
        return True


class _RefreshAdmissionLease:
    def release(self) -> None:
        pass


@pytest.mark.asyncio
async def test_ensure_fresh_detached_refresh_owns_session_on_caller_cancel(monkeypatch):
    """Regression: a client disconnect during a forced token refresh must not
    strand a background-pool connection. The shielded refresh task must write
    via its OWN session (from refresh_repo_factory), never the request-scoped
    repo that the cancelled caller closes. Pre-fix this leaked one pooled
    connection per disconnect-during-refresh (codex-lb pool-exhaustion spiral).
    """
    started = asyncio.Event()
    release = asyncio.Event()

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        started.set()
        await release.wait()
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id="acc_disconnect",
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)

    request_repo = _DummyRepo()
    owned_repo = _DummyRepo()
    scope_state = {"opened": False, "closed": False}

    @asynccontextmanager
    async def _refresh_scope() -> AsyncIterator[AccountsRepositoryPort]:
        scope_state["opened"] = True
        try:
            yield cast(AccountsRepositoryPort, owned_repo)
        finally:
            scope_state["closed"] = True

    encryptor = TokenEncryptor()
    account = Account(
        id="acc_disconnect",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=utcnow(),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    manager = AuthManager(
        cast(AccountsRepositoryPort, request_repo),
        refresh_repo_factory=_refresh_scope,
    )

    caller = asyncio.create_task(manager.ensure_fresh(account, force=True))
    await started.wait()  # refresh is in-flight
    caller.cancel()  # simulate the client disconnecting mid-refresh
    with pytest.raises(asyncio.CancelledError):
        await caller

    # The shielded refresh task survives the caller's cancellation; let it finish.
    release.set()
    for _ in range(200):
        if owned_repo.tokens_payload is not None and scope_state["closed"]:
            break
        await asyncio.sleep(0.005)

    # The refresh wrote through its OWN session and never the request-scoped one.
    assert owned_repo.tokens_payload is not None
    assert owned_repo.tokens_payload["account_id"] == "acc_disconnect"
    assert request_repo.tokens_payload is None
    # The owned session was opened and deterministically closed (connection returned).
    assert scope_state["opened"] is True
    assert scope_state["closed"] is True


@pytest.mark.asyncio
async def test_refresh_account_preserves_plan_type_when_missing(monkeypatch):
    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id="acc_1",
            plan_type=None,
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)

    encryptor = TokenEncryptor()
    account = Account(
        id="acc_1",
        email="user@example.com",
        plan_type="pro",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=utcnow(),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    updated = await manager.refresh_account(account)

    assert updated.plan_type == "pro"
    assert repo.tokens_payload is not None
    assert repo.tokens_payload["plan_type"] == "pro"


@pytest.mark.asyncio
async def test_ensure_fresh_singleflights_concurrent_refreshes(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()
    refresh_calls = 0

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        started.set()
        await release.wait()
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id="acc_sf",
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)

    encryptor = TokenEncryptor()
    stale_refresh = utcnow().replace(year=utcnow().year - 1)
    account_a = Account(
        id="acc_sf",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=stale_refresh,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    account_b = Account(**{column.name: getattr(account_a, column.name) for column in Account.__table__.columns})
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    first = asyncio.create_task(manager.ensure_fresh(account_a, force=True))
    await started.wait()
    second = asyncio.create_task(manager.ensure_fresh(account_b, force=True))
    await asyncio.sleep(0.01)
    assert not second.done()

    release.set()
    await asyncio.gather(first, second)

    assert refresh_calls == 1


@pytest.mark.asyncio
async def test_ensure_fresh_singleflights_refresh_admission_for_same_account(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()
    refresh_calls = 0
    admission_calls = 0

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        started.set()
        await release.wait()
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id="acc_sf_admission",
            plan_type="plus",
            email=None,
        )

    async def _acquire_refresh_admission():
        nonlocal admission_calls
        admission_calls += 1
        return _RefreshAdmissionLease()

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)

    encryptor = TokenEncryptor()
    stale_refresh = utcnow().replace(year=utcnow().year - 1)
    account_a = Account(
        id="acc_sf_admission",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=stale_refresh,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    account_b = Account(**{column.name: getattr(account_a, column.name) for column in Account.__table__.columns})
    repo = _DummyRepo()
    manager = AuthManager(
        cast(AccountsRepositoryPort, repo),
        acquire_refresh_admission=_acquire_refresh_admission,
    )

    first = asyncio.create_task(manager.ensure_fresh(account_a, force=True))
    await started.wait()
    second = asyncio.create_task(manager.ensure_fresh(account_b, force=True))
    await asyncio.sleep(0.01)
    assert not second.done()

    release.set()
    await asyncio.gather(first, second)

    assert refresh_calls == 1
    assert admission_calls == 1


@pytest.mark.asyncio
async def test_ensure_fresh_reuses_recent_failure_without_reissuing_refresh(monkeypatch):
    refresh_calls = 0

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        raise RefreshError("invalid_grant", "refresh failed", False)

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    monkeypatch.setattr(
        auth_manager_module,
        "get_settings",
        lambda: SimpleNamespace(proxy_refresh_failure_cooldown_seconds=30.0),
    )

    encryptor = TokenEncryptor()
    stale_refresh = utcnow().replace(year=utcnow().year - 1)
    account = Account(
        id="acc_fail_cache",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=stale_refresh,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    with pytest.raises(RefreshError):
        await manager.ensure_fresh(account, force=True)
    with pytest.raises(RefreshError):
        await manager.ensure_fresh(account, force=True)

    assert refresh_calls == 1


@pytest.mark.asyncio
async def test_ensure_fresh_does_not_reuse_recent_transport_failure(monkeypatch):
    refresh_calls = 0

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        raise RefreshError("transport_error", "temporary dns failure", False, transport_error=True)

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    monkeypatch.setattr(
        auth_manager_module,
        "get_settings",
        lambda: SimpleNamespace(proxy_refresh_failure_cooldown_seconds=30.0),
    )

    encryptor = TokenEncryptor()
    stale_refresh = utcnow().replace(year=utcnow().year - 1)
    account = Account(
        id="acc_transport_fail_cache",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=stale_refresh,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    with pytest.raises(RefreshError):
        await manager.ensure_fresh(account, force=True)
    await asyncio.sleep(0)
    with pytest.raises(RefreshError):
        await manager.ensure_fresh(account, force=True)

    assert refresh_calls == 2


@pytest.mark.asyncio
async def test_ensure_fresh_does_not_reuse_failure_after_refresh_token_changes(monkeypatch):
    refresh_calls = 0

    async def _fake_refresh(refresh_token: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        raise RefreshError("invalid_grant", f"refresh failed for {refresh_token}", False)

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    monkeypatch.setattr(
        auth_manager_module,
        "get_settings",
        lambda: SimpleNamespace(proxy_refresh_failure_cooldown_seconds=30.0),
    )

    encryptor = TokenEncryptor()
    stale_refresh = utcnow().replace(year=utcnow().year - 1)
    account = Account(
        id="acc_fail_cache_versioned",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=stale_refresh,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    with pytest.raises(RefreshError):
        await manager.ensure_fresh(account, force=True)

    account.refresh_token_encrypted = encryptor.encrypt("refresh-new")

    with pytest.raises(RefreshError) as exc_info:
        await manager.ensure_fresh(account, force=True)

    assert exc_info.value.message == "refresh failed for refresh-new"
    assert refresh_calls == 2


@pytest.mark.asyncio
async def test_refresh_account_does_not_deactivate_when_repo_has_newer_refresh_token(monkeypatch):
    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        raise RefreshError("invalid_grant", "refresh failed", True)

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)

    encryptor = TokenEncryptor()
    stale_refresh = utcnow().replace(year=utcnow().year - 1)
    stale_account = Account(
        id="acc_stale_snapshot",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=stale_refresh,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    repo = _DummyRepo()
    latest_account = Account(
        **{column.name: getattr(stale_account, column.name) for column in Account.__table__.columns}
    )
    latest_account.refresh_token_encrypted = encryptor.encrypt("refresh-new")
    repo.accounts_by_id[stale_account.id] = latest_account
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    result = await manager.refresh_account(stale_account)

    assert result is latest_account
    assert repo.status_payload is None
    assert stale_account.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_refresh_account_deactivates_when_repo_only_reencrypted_same_refresh_token(monkeypatch):
    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        raise RefreshError("invalid_grant", "refresh failed", True)

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    invalidated_accounts: list[str] = []
    cache_invalidations: list[str] = []

    async def _invalidate_account_client(account_id: str) -> None:
        invalidated_accounts.append(account_id)

    monkeypatch.setattr(auth_manager_module, "invalidate_account_client", _invalidate_account_client)
    monkeypatch.setattr(
        auth_manager_module,
        "get_account_selection_cache",
        lambda: SimpleNamespace(invalidate=lambda: cache_invalidations.append("cache")),
    )

    encryptor = TokenEncryptor()
    stale_refresh = utcnow().replace(year=utcnow().year - 1)
    stale_account = Account(
        id="acc_same_token_reencrypted",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-same"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=stale_refresh,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    repo = _DummyRepo()
    latest_account = Account(
        **{column.name: getattr(stale_account, column.name) for column in Account.__table__.columns}
    )
    latest_account.refresh_token_encrypted = encryptor.encrypt("refresh-same")
    repo.accounts_by_id[stale_account.id] = latest_account
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    with pytest.raises(RefreshError) as exc_info:
        await manager.refresh_account(stale_account)

    assert exc_info.value.is_permanent is True
    assert repo.status_payload is not None
    assert repo.status_payload["status"] == AccountStatus.DEACTIVATED
    assert invalidated_accounts == [stale_account.id]
    assert cache_invalidations == ["cache"]


@pytest.mark.parametrize(
    ("error_code", "error_message"),
    [
        ("token_expired", "Provided authentication token is expired. Please try signing in again."),
        ("app_session_terminated", "Your session has ended. Please log in again."),
    ],
)
@pytest.mark.asyncio
async def test_refresh_account_deactivates_when_upstream_returns_permanent_session_error(
    monkeypatch,
    error_code: str,
    error_message: str,
):
    """Refresh-bound session failures must deactivate the account instead of
    looping retries forever while the account stays ``ACTIVE``.
    """

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        from app.core.auth.refresh import classify_refresh_error

        assert classify_refresh_error(error_code) is True
        raise RefreshError(error_code, error_message, classify_refresh_error(error_code))

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)

    encryptor = TokenEncryptor()
    stale_refresh = utcnow().replace(year=utcnow().year - 1)
    expired_account = Account(
        id=f"acc_{error_code}",
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=stale_refresh,
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )
    repo = _DummyRepo()
    latest_account = Account(
        **{column.name: getattr(expired_account, column.name) for column in Account.__table__.columns}
    )
    repo.accounts_by_id[expired_account.id] = latest_account
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    with pytest.raises(RefreshError) as exc_info:
        await manager.refresh_account(expired_account)

    assert exc_info.value.code == error_code
    assert exc_info.value.is_permanent is True
    assert repo.status_payload is not None
    assert repo.status_payload["status"] == AccountStatus.DEACTIVATED
    reason = repo.status_payload["deactivation_reason"]
    assert isinstance(reason, str)
    assert "re-login" in reason.lower() or "expired" in reason.lower()


@pytest.fixture(autouse=True)
def _reset_token_refresh_scheduler_state() -> None:
    set_scheduler_now_override(None)
    set_scheduler_monotonic_override(None)
    set_background_pacer_override(None)
    reset_background_token_refresh_pacer()


def _stale_account(account_id: str) -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        email="user@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access-old"),
        refresh_token_encrypted=encryptor.encrypt("refresh-old"),
        id_token_encrypted=encryptor.encrypt("id-old"),
        last_refresh=utcnow().replace(year=utcnow().year - 1),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
        token_refresh_failure_count=0,
    )


@pytest.mark.asyncio
async def test_ensure_fresh_live_request_bypasses_background_pacer(monkeypatch) -> None:
    pacer_acquires = 0

    class _TrackingPacer(BackgroundTokenRefreshPacer):
        async def acquire(self):  # type: ignore[override]
            nonlocal pacer_acquires
            pacer_acquires += 1
            return await super().acquire()

    set_background_pacer_override(_TrackingPacer(concurrency=1, min_start_spacing_seconds=300.0))

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id=account_id,
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))
    account = _stale_account("acc_live_bypass")

    await manager.ensure_fresh(account, force=True, source=TokenRefreshSource.LIVE_REQUEST)

    assert pacer_acquires == 0
    assert repo.schedule_payload is not None
    assert repo.schedule_payload["token_refresh_last_result"] == "success"


@pytest.mark.asyncio
async def test_ensure_fresh_background_defers_when_schedule_not_due(monkeypatch) -> None:
    now = utcnow()
    set_scheduler_now_override(now)
    account = _stale_account("acc_bg_defer")
    account.last_refresh = now - timedelta(days=1)
    account.token_refresh_next_allowed_at = now.replace(year=now.year + 1)

    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    with pytest.raises(TokenRefreshDeferred):
        await manager.ensure_fresh(account, force=True, source=TokenRefreshSource.USAGE_REFRESH_401)


@pytest.mark.asyncio
async def test_ensure_fresh_background_records_transient_failure_backoff(monkeypatch) -> None:
    now = utcnow()
    set_scheduler_now_override(now)
    account = _stale_account("acc_bg_fail")
    account.token_refresh_next_allowed_at = now.replace(year=now.year - 1)

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        raise RefreshError("transport_error", "temporary", False, transport_error=True)

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    set_background_pacer_override(BackgroundTokenRefreshPacer(concurrency=1, min_start_spacing_seconds=0.0))

    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))

    with pytest.raises(RefreshError):
        await manager.ensure_fresh(account, force=True, source=TokenRefreshSource.USAGE_REFRESH_401)

    assert repo.schedule_payload is not None
    assert repo.schedule_payload["token_refresh_last_result"] == "failure"
    assert repo.schedule_payload["token_refresh_failure_count"] == 1
    assert repo.schedule_payload["token_refresh_next_allowed_at"] is not None
    assert repo.schedule_payload["token_refresh_next_allowed_at"] > now


@pytest.mark.asyncio
async def test_ensure_fresh_background_singleflights_before_pacer_wait(monkeypatch) -> None:
    now = utcnow()
    set_scheduler_now_override(now)
    set_background_pacer_override(BackgroundTokenRefreshPacer(concurrency=1, min_start_spacing_seconds=0.0))
    started = asyncio.Event()
    release = asyncio.Event()
    refresh_calls = 0

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        started.set()
        await release.wait()
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id=account_id,
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))
    account = _stale_account("acc_bg_singleflight")
    account.token_refresh_next_allowed_at = now - timedelta(seconds=1)

    first = asyncio.create_task(manager.ensure_fresh(account, force=True, source=TokenRefreshSource.USAGE_REFRESH_401))
    await started.wait()
    second = asyncio.create_task(manager.ensure_fresh(account, force=True, source=TokenRefreshSource.USAGE_REFRESH_401))
    await asyncio.sleep(0)

    release.set()
    await asyncio.gather(first, second)

    assert refresh_calls == 1


@pytest.mark.asyncio
async def test_ensure_fresh_success_persists_schedule_atomically_with_tokens(monkeypatch) -> None:
    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id=account_id,
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    set_background_pacer_override(BackgroundTokenRefreshPacer(concurrency=1, min_start_spacing_seconds=0.0))

    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))
    account = _stale_account("acc_atomic")

    await manager.ensure_fresh(account, force=True, source=TokenRefreshSource.LIVE_REQUEST)

    assert repo.tokens_payload is not None
    assert repo.tokens_payload["token_refresh_schedule"] is not None
    assert repo.schedule_payload is not None
    assert repo.schedule_payload["token_refresh_last_result"] == "success"
    assert repo.schedule_payload["token_refresh_last_reason"] == "live_request"
    assert repo.schedule_only_calls == 0


@pytest.mark.asyncio
async def test_ensure_fresh_live_request_skips_refresh_when_not_due(monkeypatch) -> None:
    refresh_calls = 0

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id=account_id,
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))
    account = _stale_account("acc_fresh")
    account.last_refresh = utcnow()

    result = await manager.ensure_fresh(account, source=TokenRefreshSource.LIVE_REQUEST)

    assert refresh_calls == 0
    assert result.id == account.id
    assert repo.tokens_payload is None


@pytest.mark.asyncio
async def test_ensure_fresh_live_request_does_not_rewrite_existing_schedule_when_not_due(monkeypatch) -> None:
    refresh_calls = 0
    now = utcnow()

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id=account_id,
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))
    account = _stale_account("acc_fresh_existing_schedule")
    account.last_refresh = now
    account.token_refresh_next_allowed_at = now + timedelta(days=1)

    result = await manager.ensure_fresh(account, source=TokenRefreshSource.LIVE_REQUEST)

    assert refresh_calls == 0
    assert result.id == account.id
    assert repo.tokens_payload is None
    assert repo.schedule_only_calls == 0
    assert repo.schedule_payload is None


@pytest.mark.asyncio
async def test_ensure_fresh_background_returns_scheduled_account_when_not_forced(monkeypatch) -> None:
    refresh_calls = 0
    now = utcnow()
    set_scheduler_now_override(now)

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id=account_id,
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))
    account = _stale_account("acc_bg_scheduled")
    offset_seconds = refresh_jitter_offset_seconds(account.id, jitter_hours=18.0)
    account.last_refresh = now - timedelta(days=8) + timedelta(seconds=offset_seconds - 1)
    account.token_refresh_next_allowed_at = now + timedelta(hours=1)

    result = await manager.ensure_fresh(account, source=TokenRefreshSource.STARTUP)

    assert refresh_calls == 0
    assert result.id == account.id
    assert repo.tokens_payload is None


@pytest.mark.asyncio
async def test_ensure_fresh_background_returns_fresh_account_without_defer(monkeypatch) -> None:
    refresh_calls = 0

    async def _fake_refresh(_: str, *, account_id: str | None = None) -> TokenRefreshResult:
        nonlocal refresh_calls
        refresh_calls += 1
        return TokenRefreshResult(
            access_token="new-access",
            refresh_token="new-refresh",
            id_token="new-id",
            account_id=account_id,
            plan_type="plus",
            email=None,
        )

    monkeypatch.setattr(auth_manager_module, "refresh_access_token", _fake_refresh)
    repo = _DummyRepo()
    manager = AuthManager(cast(AccountsRepositoryPort, repo))
    account = _stale_account("acc_bg_fresh")
    account.last_refresh = utcnow()

    result = await manager.ensure_fresh(account, source=TokenRefreshSource.STARTUP)

    assert refresh_calls == 0
    assert result.id == account.id
    assert repo.tokens_payload is None
