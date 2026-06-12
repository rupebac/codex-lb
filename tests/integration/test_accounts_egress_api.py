"""Integration tests for account egress verification API."""

from __future__ import annotations

import base64
import json

import pytest

from app.core.clients import account_egress_probe as egress_probe_module
from app.core.config.settings import get_settings
from app.db.session import SessionLocal
from app.modules.accounts.repository import AccountsRepository

pytestmark = pytest.mark.integration


def _encode_jwt(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"header.{body}.sig"


async def _import_account(async_client, *, email: str = "egress@example.com", account_id: str = "acc_egress") -> str:
    auth_json = {
        "tokens": {
            "idToken": _encode_jwt(
                {
                    "email": email,
                    "https://api.openai.com/auth": {"chatgpt_plan_type": "plus"},
                }
            ),
            "accessToken": "access",
            "refreshToken": "refresh",
            "accountId": account_id,
        },
    }
    files = {"auth_json": ("auth.json", json.dumps(auth_json), "application/json")}
    response = await async_client.post("/api/accounts/import", files=files)
    assert response.status_code == 200
    return response.json()["accountId"]


@pytest.fixture(autouse=True)
def _reset_egress_http_get():
    egress_probe_module._set_http_get_for_test(None)
    yield
    egress_probe_module._set_http_get_for_test(None)


@pytest.mark.asyncio
async def test_get_account_egress_report_lists_all_accounts(async_client) -> None:
    account_id = await _import_account(async_client)
    response = await async_client.get("/api/accounts/egress")
    assert response.status_code == 200
    payload = response.json()
    assert payload["unknownCount"] >= 1
    assert any(entry["accountId"] == account_id for entry in payload["accounts"])


@pytest.mark.asyncio
async def test_probe_account_egress_persists_observed_ip(async_client, monkeypatch) -> None:
    account_id = await _import_account(async_client, email="probe@example.com", account_id="acc_probe_ok")

    async def _stub(account_id: str, probe_url: str, timeout_seconds: float) -> tuple[int, str]:
        return 200, '{"ip":"93.184.216.34"}'

    egress_probe_module._set_http_get_for_test(_stub)

    response = await async_client.post(f"/api/accounts/{account_id}/egress/probe")
    assert response.status_code == 200
    payload = response.json()
    assert payload["accountId"] == account_id
    assert payload["status"] == "direct_egress"
    assert payload["observedIp"] == "93.184.216.34"
    assert payload["checkedAt"] is not None

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        account = await repo.get_by_id(account_id)
        assert account is not None
        assert account.egress_last_observed_ip == "93.184.216.34"
        assert account.egress_last_probe_status == "ok"


@pytest.mark.asyncio
async def test_probe_disabled_returns_422(async_client, monkeypatch) -> None:
    account_id = await _import_account(async_client, email="disabled@example.com", account_id="acc_probe_disabled")
    settings = get_settings()
    monkeypatch.setattr(settings, "account_egress_probe_enabled", False)

    response = await async_client.post(f"/api/accounts/{account_id}/egress/probe")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "egress_probe_disabled"


@pytest.mark.asyncio
async def test_failed_probe_returns_checked_time_and_clears_observed_ip(async_client) -> None:
    account_id = await _import_account(async_client, email="fail@example.com", account_id="acc_probe_fail")

    async def _ok_stub(account_id: str, probe_url: str, timeout_seconds: float) -> tuple[int, str]:
        return 200, '{"ip":"93.184.216.34"}'

    egress_probe_module._set_http_get_for_test(_ok_stub)
    ok_response = await async_client.post(f"/api/accounts/{account_id}/egress/probe")
    assert ok_response.status_code == 200
    assert ok_response.json()["observedIp"] == "93.184.216.34"

    async def _fail_stub(account_id: str, probe_url: str, timeout_seconds: float) -> tuple[int, str]:
        return 200, '{"ip":"10.0.0.1"}'

    egress_probe_module._set_http_get_for_test(_fail_stub)
    response = await async_client.post(f"/api/accounts/{account_id}/egress/probe")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "probe_failed"
    assert payload["observedIp"] is None
    assert payload["checkedAt"] is not None
    assert payload["error"] == "invalid_or_non_global_ip"

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        account = await repo.get_by_id(account_id)
        assert account is not None
        assert account.egress_last_observed_ip is None
        assert account.egress_last_observed_at is None
        assert account.egress_last_checked_at is not None
        assert account.egress_last_probe_status == "probe_failed"
