"""Account-bound egress IP probe.

Unlike :mod:`account_proxy_probe` (save-time SOCKS5 + OAuth validation), this
module exercises the **persisted** per-account HTTP client registry via
:func:`lease_account_http_client` and records the globally routable public IP
observed through that path.
"""

from __future__ import annotations

import ipaddress
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import aiohttp

from app.core.clients.account_http import lease_account_http_client
from app.core.config.settings import Settings, get_settings
from app.core.utils.time import utcnow

logger = logging.getLogger(__name__)

_HTTP_GET = Callable[
    [str, str, float],
    Awaitable[tuple[int, str]],
]
_http_get_override: _HTTP_GET | None = None


@dataclass(frozen=True, slots=True)
class EgressProbeResult:
    ok: bool
    observed_ip: str | None = None
    error: str | None = None
    checked_at: datetime | None = None


def _set_http_get_for_test(factory: _HTTP_GET | None) -> None:
    global _http_get_override
    _http_get_override = factory


def parse_observed_ip(body: str) -> str | None:
    """Parse a globally routable public IP from JSON or plain-text probe bodies."""

    stripped = body.strip()
    if not stripped:
        return None

    candidate: str | None = None
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            raw_ip = payload.get("ip")
            if isinstance(raw_ip, str):
                candidate = raw_ip.strip()
    else:
        candidate = stripped.split()[0]

    if not candidate:
        return None

    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if not parsed.is_global:
        return None
    return str(parsed)


async def _fetch_probe_body(account_id: str, probe_url: str, timeout_seconds: float) -> tuple[int, str]:
    if _http_get_override is not None:
        return await _http_get_override(account_id, probe_url, timeout_seconds)

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    async with lease_account_http_client(account_id) as client:
        async with client.session.get(probe_url, timeout=timeout) as resp:
            return resp.status, await resp.text()


async def probe_account_egress_ip(
    account_id: str,
    *,
    settings: Settings | None = None,
) -> EgressProbeResult:
    """Probe the account-bound egress path and return the observed public IP."""

    effective_settings = settings or get_settings()
    probe_url = effective_settings.account_egress_probe_url
    timeout_seconds = float(effective_settings.account_egress_probe_timeout_seconds)
    checked_at = utcnow()

    try:
        status, body = await _fetch_probe_body(account_id, probe_url, timeout_seconds)
    except Exception as exc:  # pragma: no cover - defensive transport catch
        logger.warning(
            "Egress probe transport failure account_id=%s url=%s: %s",
            account_id,
            probe_url,
            exc,
        )
        return EgressProbeResult(ok=False, error=_short_detail(exc), checked_at=checked_at)

    if not (200 <= status < 300):
        return EgressProbeResult(
            ok=False,
            error=f"probe_http_{status}",
            checked_at=checked_at,
        )

    observed_ip = parse_observed_ip(body)
    if observed_ip is None:
        return EgressProbeResult(
            ok=False,
            error="invalid_or_non_global_ip",
            checked_at=checked_at,
        )

    return EgressProbeResult(ok=True, observed_ip=observed_ip, checked_at=checked_at)


def _short_detail(exc: BaseException) -> str:
    message = str(exc) or exc.__class__.__name__
    return message[:200]
