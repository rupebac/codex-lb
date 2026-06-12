"""Unit tests for egress guardrail filtering in load balancer selection inputs."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config.settings import Settings
from app.db.models import Account, AccountStatus
from app.modules.proxy.load_balancer import LoadBalancer

pytestmark = pytest.mark.unit


def _account(account_id: str, *, observed_ip: str | None = None, probe_status: str = "unknown") -> Account:
    return Account(
        id=account_id,
        email=f"{account_id}@example.com",
        plan_type="plus",
        access_token_encrypted=b"a",
        refresh_token_encrypted=b"r",
        id_token_encrypted=b"i",
        last_refresh=datetime.now(timezone.utc),
        status=AccountStatus.ACTIVE,
        egress_last_observed_ip=observed_ip,
        egress_last_observed_at=datetime.now(timezone.utc) if observed_ip else None,
        egress_last_checked_at=datetime.now(timezone.utc) if observed_ip else None,
        egress_last_probe_status=probe_status,
    )


@pytest.mark.asyncio
async def test_load_selection_inputs_excludes_direct_egress_in_block_mode() -> None:
    direct = _account("direct", observed_ip="1.2.3.4", probe_status="ok")
    unknown = _account("unknown")

    mock_accounts_repo = AsyncMock()
    mock_accounts_repo.list_accounts = AsyncMock(return_value=[direct, unknown])

    mock_usage_repo = AsyncMock()
    mock_usage_repo.latest_by_account = AsyncMock(return_value={})

    mock_repos = MagicMock()
    mock_repos.accounts = mock_accounts_repo
    mock_repos.usage = mock_usage_repo
    mock_repos.__aenter__ = AsyncMock(return_value=mock_repos)
    mock_repos.__aexit__ = AsyncMock(return_value=None)

    balancer = LoadBalancer(repo_factory=lambda: mock_repos)
    block_settings = Settings(account_egress_guardrail_mode="block")

    with patch("app.modules.proxy.load_balancer.get_settings", return_value=block_settings):
        selection_inputs = await balancer._load_selection_inputs(model=None)

    assert [account.id for account in selection_inputs.accounts] == ["unknown"]
