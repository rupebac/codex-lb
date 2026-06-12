from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.core.auth import DEFAULT_PLAN
from app.core.crypto import TokenEncryptor
from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus
from app.db.session import SessionLocal
from app.modules.accounts.repository import AccountsRepository

pytestmark = pytest.mark.integration


def _make_account(account_id: str, email: str) -> Account:
    encryptor = TokenEncryptor()
    return Account(
        id=account_id,
        email=email,
        plan_type=DEFAULT_PLAN,
        access_token_encrypted=encryptor.encrypt("access"),
        refresh_token_encrypted=encryptor.encrypt("refresh"),
        id_token_encrypted=encryptor.encrypt("id"),
        last_refresh=utcnow(),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )


@pytest.mark.asyncio
async def test_token_refresh_schedule_columns_exist_after_upgrade(db_setup) -> None:
    async with SessionLocal() as session:
        result = await session.execute(text("PRAGMA table_info(accounts)"))
        columns = {row[1] for row in result.fetchall()}

    expected = {
        "token_refresh_next_allowed_at",
        "token_refresh_last_attempt_at",
        "token_refresh_last_result",
        "token_refresh_last_reason",
        "token_refresh_failure_count",
    }
    assert expected.issubset(columns)


@pytest.mark.asyncio
async def test_historical_accounts_backfill_failure_count_zero(db_setup) -> None:
    account_id = f"acc_hist_{uuid.uuid4().hex[:8]}"
    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        await repo.upsert(_make_account(account_id, f"{account_id}@example.com"))

    async with SessionLocal() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        assert account.token_refresh_failure_count == 0
        assert account.token_refresh_next_allowed_at is None
