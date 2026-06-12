from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.auth.token_refresh_scheduler import TokenRefreshDeferred, TokenRefreshSource
from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus
from app.modules.usage.updater import AccountRefreshResult, UsageUpdater

pytestmark = pytest.mark.unit


class StubUsageRepository:
    def __init__(self) -> None:
        self.entries: list[object] = []

    async def latest_entry_for_account(self, account_id: str, *, window: str | None = None) -> None:
        return None

    async def add_entry(self, *args: object, **kwargs: object) -> None:
        self.entries.append((args, kwargs))
        return None


class StubAccountsRepository:
    def __init__(self) -> None:
        self.accounts_by_id: dict[str, Account] = {}


class _AuthManagerStub:
    async def ensure_fresh(self, account: Account, *, force: bool = False, source: TokenRefreshSource) -> Account:
        raise TokenRefreshDeferred("scheduled", next_allowed_at=utcnow())


def _make_account(account_id: str) -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        chatgpt_account_id=f"workspace_{account_id}",
        email="usage@example.com",
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access"),
        refresh_token_encrypted=encryptor.encrypt("refresh"),
        id_token_encrypted=encryptor.encrypt("id"),
        last_refresh=datetime.now(tz=timezone.utc),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )


@pytest.mark.asyncio
async def test_usage_refresh_401_repair_treats_scheduler_deferral_as_non_success(monkeypatch) -> None:
    monkeypatch.setenv("CODEX_LB_USAGE_REFRESH_ENABLED", "true")
    from app.core.clients.usage import UsageFetchError
    from app.core.config.settings import get_settings

    get_settings.cache_clear()

    async def stub_fetch_usage(**_: Any) -> None:
        raise UsageFetchError(401, "Unauthorized")

    monkeypatch.setattr("app.modules.usage.updater.fetch_usage", stub_fetch_usage)

    usage_repo = StubUsageRepository()
    accounts_repo = StubAccountsRepository()
    updater = UsageUpdater(usage_repo, accounts_repo=accounts_repo)
    updater._auth_manager = _AuthManagerStub()

    account = _make_account("acc_deferred")
    accounts_repo.accounts_by_id[account.id] = account

    result = await updater._refresh_account(account, usage_account_id=account.chatgpt_account_id)

    assert result == AccountRefreshResult(usage_written=False, fetch_succeeded=False)
    assert account.status == AccountStatus.ACTIVE
    assert len(usage_repo.entries) == 0
