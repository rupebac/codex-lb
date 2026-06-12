"""Integration tests for egress probe persistence on accounts."""

from __future__ import annotations

import pytest
from sqlalchemy import select

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
        plan_type="plus",
        access_token_encrypted=encryptor.encrypt("access"),
        refresh_token_encrypted=encryptor.encrypt("refresh"),
        id_token_encrypted=encryptor.encrypt("id"),
        last_refresh=utcnow(),
        status=AccountStatus.ACTIVE,
        deactivation_reason=None,
    )


@pytest.mark.asyncio
async def test_update_egress_probe_result_success(db_setup) -> None:
    checked_at = utcnow()
    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        await repo.upsert(_make_account("acc_egress_ok", "egress@example.com"))

        ok = await repo.update_egress_probe_result(
            "acc_egress_ok",
            observed_ip="93.184.216.34",
            observed_at=checked_at,
            checked_at=checked_at,
            probe_status="ok",
            probe_error=None,
        )
        assert ok is True

        row = (await session.execute(select(Account).where(Account.id == "acc_egress_ok"))).scalar_one()
        assert row.egress_last_observed_ip == "93.184.216.34"
        assert row.egress_last_observed_at == checked_at
        assert row.egress_last_checked_at == checked_at
        assert row.egress_last_probe_status == "ok"
        assert row.egress_last_probe_error is None


@pytest.mark.asyncio
async def test_update_egress_probe_result_failure_clears_observed_ip(db_setup) -> None:
    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        await repo.upsert(_make_account("acc_egress_fail", "fail@example.com"))
        await repo.update_egress_probe_result(
            "acc_egress_fail",
            observed_ip="1.2.3.4",
            observed_at=utcnow(),
            checked_at=utcnow(),
            probe_status="ok",
            probe_error=None,
        )
        checked_at = utcnow()

        ok = await repo.update_egress_probe_result(
            "acc_egress_fail",
            observed_ip=None,
            observed_at=None,
            checked_at=checked_at,
            probe_status="probe_failed",
            probe_error="invalid_or_non_global_ip",
        )
        assert ok is True

        row = (await session.execute(select(Account).where(Account.id == "acc_egress_fail"))).scalar_one()
        assert row.egress_last_observed_ip is None
        assert row.egress_last_observed_at is None
        assert row.egress_last_checked_at == checked_at
        assert row.egress_last_probe_status == "probe_failed"
        assert row.egress_last_probe_error == "invalid_or_non_global_ip"
