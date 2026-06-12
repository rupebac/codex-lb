from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.core.auth.refresh import next_refresh_eligible_at, should_refresh
from app.core.config.settings import get_settings
from app.core.utils.time import to_utc_naive, utcnow
from app.db.models import Account, AccountStatus

_TOKEN_REFRESH_SPREAD_SALT = b"codex-lb:token-refresh-spread:v1"
_TOKEN_REFRESH_BACKOFF_JITTER_SALT = b"codex-lb:token-refresh-backoff-jitter:v1"

logger = logging.getLogger(__name__)

_SCHEDULE_UNSET = object()

_NOW_OVERRIDE: datetime | None = None
_MONOTONIC_OVERRIDE: float | None = None
_PACER_OVERRIDE: "BackgroundTokenRefreshPacer | None" = None


class TokenRefreshSource(StrEnum):
    LIVE_REQUEST = "live_request"
    USAGE_REFRESH_401 = "usage_refresh_401"
    AUTH_GUARDIAN = "auth_guardian"  # reserved until auth guardian is implemented
    MANUAL = "manual"  # reserved for operator-initiated fleet refresh
    WARMUP = "warmup"
    STARTUP = "startup"


class TokenRefreshDeferred(Exception):
    """Background refresh was deferred by schedule, policy, or pacer."""

    def __init__(self, reason: str, *, next_allowed_at: datetime | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.next_allowed_at = next_allowed_at


@dataclass(frozen=True)
class TokenRefreshDecision:
    allowed: bool
    reason: str
    next_allowed_at: datetime | None
    bypass_background_pacer: bool = False
    initialized_schedule: bool = False


@dataclass(frozen=True)
class TokenRefreshScheduleUpdate:
    next_allowed_at: datetime | None | object = _SCHEDULE_UNSET
    last_attempt_at: datetime | None | object = _SCHEDULE_UNSET
    last_result: str | None | object = _SCHEDULE_UNSET
    last_reason: str | None | object = _SCHEDULE_UNSET
    failure_count: int | object = _SCHEDULE_UNSET

    def repo_field_names(self) -> tuple[str, ...]:
        names: list[str] = []
        for name in (
            "next_allowed_at",
            "last_attempt_at",
            "last_result",
            "last_reason",
            "failure_count",
        ):
            if getattr(self, name) is not _SCHEDULE_UNSET:
                names.append(name)
        return tuple(names)


class BackgroundTokenRefreshPacerLease:
    def __init__(self, pacer: "BackgroundTokenRefreshPacer") -> None:
        self._pacer = pacer
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._pacer._release_slot()


class BackgroundTokenRefreshPacer:
    """Process-local pacer for background OAuth refresh starts."""

    def __init__(
        self,
        *,
        concurrency: int,
        min_start_spacing_seconds: float,
    ) -> None:
        self._concurrency = max(1, concurrency)
        self._min_start_spacing_seconds = max(0.0, min_start_spacing_seconds)
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._lock = asyncio.Lock()
        self._last_start_monotonic: float | None = None

    async def acquire(self) -> BackgroundTokenRefreshPacerLease:
        while True:
            await self._semaphore.acquire()
            wait_seconds = 0.0
            try:
                async with self._lock:
                    now_mono = _monotonic_now()
                    if self._last_start_monotonic is not None:
                        elapsed = now_mono - self._last_start_monotonic
                        wait_seconds = self._min_start_spacing_seconds - elapsed
                    if wait_seconds <= 0:
                        self._last_start_monotonic = now_mono
                        return BackgroundTokenRefreshPacerLease(self)
            except BaseException:
                self._semaphore.release()
                raise
            self._semaphore.release()
            await asyncio.sleep(wait_seconds)

    def _release_slot(self) -> None:
        self._semaphore.release()


_BACKGROUND_PACER: BackgroundTokenRefreshPacer | None = None


def get_background_token_refresh_pacer() -> BackgroundTokenRefreshPacer:
    global _BACKGROUND_PACER
    if _PACER_OVERRIDE is not None:
        return _PACER_OVERRIDE
    if _BACKGROUND_PACER is None:
        settings = get_settings()
        _BACKGROUND_PACER = BackgroundTokenRefreshPacer(
            concurrency=settings.account_token_refresh_background_concurrency,
            min_start_spacing_seconds=settings.account_token_refresh_min_start_spacing_seconds,
        )
    return _BACKGROUND_PACER


def reset_background_token_refresh_pacer() -> None:
    global _BACKGROUND_PACER
    _BACKGROUND_PACER = None


def _monotonic_now() -> float:
    if _MONOTONIC_OVERRIDE is not None:
        return _MONOTONIC_OVERRIDE
    return time.monotonic()


def scheduler_now() -> datetime:
    if _NOW_OVERRIDE is not None:
        return _NOW_OVERRIDE
    return utcnow()


def set_scheduler_now_override(value: datetime | None) -> None:
    global _NOW_OVERRIDE
    _NOW_OVERRIDE = value


def set_scheduler_monotonic_override(value: float | None) -> None:
    global _MONOTONIC_OVERRIDE
    _MONOTONIC_OVERRIDE = value


def set_background_pacer_override(pacer: BackgroundTokenRefreshPacer | None) -> None:
    global _PACER_OVERRIDE
    _PACER_OVERRIDE = pacer


def _stable_fraction(account_id: str, salt: bytes) -> float:
    digest = hashlib.sha256(salt + account_id.encode("utf-8")).digest()
    raw = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return (raw % 1_000_000_007) / 1_000_000_007


def compute_initial_next_allowed_at(account_id: str, *, now: datetime | None = None) -> datetime:
    settings = get_settings()
    current = to_utc_naive(now) if now is not None else scheduler_now()
    spread_hours = float(settings.account_token_refresh_initial_spread_hours)
    if spread_hours <= 0.0:
        return current
    offset_seconds = _stable_fraction(account_id, _TOKEN_REFRESH_SPREAD_SALT) * spread_hours * 3600.0
    return current + timedelta(seconds=offset_seconds)


def is_past_hard_max_refresh(last_refresh: datetime, *, now: datetime | None = None) -> bool:
    settings = get_settings()
    current = to_utc_naive(now) if now is not None else scheduler_now()
    last = to_utc_naive(last_refresh)
    interval_days = settings.token_refresh_interval_days or 8
    return current - last > timedelta(days=interval_days)


def compute_failure_backoff_at(
    failure_count: int,
    account_id: str,
    *,
    now: datetime | None = None,
) -> datetime:
    settings = get_settings()
    current = to_utc_naive(now) if now is not None else scheduler_now()
    base_seconds = float(settings.account_token_refresh_failure_backoff_base_seconds)
    max_seconds = float(settings.account_token_refresh_failure_backoff_max_seconds)
    exponent = max(0, failure_count - 1)
    delay = min(max_seconds, base_seconds * (2**exponent))
    jitter_seconds = _stable_fraction(account_id, _TOKEN_REFRESH_BACKOFF_JITTER_SALT) * base_seconds
    return current + timedelta(seconds=delay + jitter_seconds)


def _background_skip_reason(account: Account) -> str | None:
    if account.status == AccountStatus.DEACTIVATED:
        return "skipped_status"
    if account.status == AccountStatus.PAUSED:
        return "skipped_status"
    if account.status == AccountStatus.REAUTH_REQUIRED:
        return "skipped_status"
    settings = get_settings()
    if (
        account.status == AccountStatus.QUOTA_EXCEEDED
        and not settings.account_token_refresh_background_refresh_quota_exceeded
    ):
        return "skipped_quota"
    return None


_BACKGROUND_DEFER_REFRESH_REASONS = frozenset({"scheduled", "skipped_status", "skipped_quota"})


def is_background_refresh_deferred(reason: str) -> bool:
    """Return True when a background caller should stop and retry later."""

    return reason in _BACKGROUND_DEFER_REFRESH_REASONS


def evaluate_refresh_decision(
    account: Account,
    *,
    source: TokenRefreshSource,
    force: bool = False,
    now: datetime | None = None,
) -> TokenRefreshDecision:
    current = to_utc_naive(now) if now is not None else scheduler_now()

    if source is TokenRefreshSource.LIVE_REQUEST:
        if not force and not should_refresh(account.last_refresh, current, account_id=account.id):
            return TokenRefreshDecision(
                allowed=False,
                reason="not_due",
                next_allowed_at=account.token_refresh_next_allowed_at,
                bypass_background_pacer=True,
            )
        return TokenRefreshDecision(
            allowed=True,
            reason="started",
            next_allowed_at=account.token_refresh_next_allowed_at,
            bypass_background_pacer=True,
        )

    skip_reason = _background_skip_reason(account)
    if skip_reason is not None:
        return TokenRefreshDecision(
            allowed=False,
            reason=skip_reason,
            next_allowed_at=account.token_refresh_next_allowed_at,
        )

    next_allowed = account.token_refresh_next_allowed_at
    initialized = False
    if next_allowed is None:
        next_allowed = compute_initial_next_allowed_at(account.id, now=current)
        initialized = True

    past_hard_max = is_past_hard_max_refresh(account.last_refresh, now=current)
    due_by_interval = force or should_refresh(account.last_refresh, current, account_id=account.id)
    if not due_by_interval and not past_hard_max:
        return TokenRefreshDecision(
            allowed=False,
            reason="not_due",
            next_allowed_at=next_allowed,
            initialized_schedule=initialized,
        )

    if next_allowed is not None and to_utc_naive(next_allowed) > current and not past_hard_max:
        return TokenRefreshDecision(
            allowed=False,
            reason="scheduled",
            next_allowed_at=next_allowed,
            initialized_schedule=initialized,
        )

    return TokenRefreshDecision(
        allowed=True,
        reason="started",
        next_allowed_at=next_allowed,
        initialized_schedule=initialized,
    )


def build_success_schedule_update(
    account: Account,
    *,
    source: TokenRefreshSource,
    attempt_at: datetime,
    last_refresh: datetime,
) -> TokenRefreshScheduleUpdate:
    return TokenRefreshScheduleUpdate(
        next_allowed_at=next_refresh_eligible_at(last_refresh, account_id=account.id),
        last_attempt_at=attempt_at,
        last_result="success",
        last_reason=source.value,
        failure_count=0,
    )


def build_failure_schedule_update(
    account: Account,
    *,
    source: TokenRefreshSource,
    attempt_at: datetime,
    is_permanent: bool,
) -> TokenRefreshScheduleUpdate:
    new_failure_count = (account.token_refresh_failure_count or 0) + 1
    if is_permanent:
        next_allowed = account.token_refresh_next_allowed_at
    else:
        next_allowed = compute_failure_backoff_at(new_failure_count, account.id, now=attempt_at)
    return TokenRefreshScheduleUpdate(
        next_allowed_at=next_allowed,
        last_attempt_at=attempt_at,
        last_result="failure",
        last_reason=source.value,
        failure_count=new_failure_count,
    )


def build_skip_schedule_update(
    *,
    source: TokenRefreshSource,
    reason: str,
    attempt_at: datetime,
    next_allowed_at: datetime | None,
    initialized_schedule: bool,
) -> TokenRefreshScheduleUpdate | None:
    if reason.startswith("skipped"):
        return TokenRefreshScheduleUpdate(
            next_allowed_at=next_allowed_at,
            last_attempt_at=attempt_at,
            last_result="skipped",
            last_reason=source.value,
        )
    if initialized_schedule and next_allowed_at is not None:
        return TokenRefreshScheduleUpdate(next_allowed_at=next_allowed_at)
    return None


_ACCOUNT_SCHEDULE_FIELD_MAP = {
    "next_allowed_at": "token_refresh_next_allowed_at",
    "last_attempt_at": "token_refresh_last_attempt_at",
    "last_result": "token_refresh_last_result",
    "last_reason": "token_refresh_last_reason",
    "failure_count": "token_refresh_failure_count",
}


def schedule_update_to_db_values(update: TokenRefreshScheduleUpdate) -> dict[str, object]:
    values: dict[str, object] = {}
    for field_name in update.repo_field_names():
        value = getattr(update, field_name)
        if value is _SCHEDULE_UNSET:
            continue
        values[_ACCOUNT_SCHEDULE_FIELD_MAP[field_name]] = value
    return values


def apply_schedule_update_to_account(account: Account, update: TokenRefreshScheduleUpdate) -> None:
    for field_name in update.repo_field_names():
        value = getattr(update, field_name)
        if value is _SCHEDULE_UNSET:
            continue
        setattr(account, _ACCOUNT_SCHEDULE_FIELD_MAP[field_name], value)


def log_refresh_decision(
    account_id: str,
    *,
    source: TokenRefreshSource,
    decision: str,
    next_allowed_at: datetime | None,
    failure_count: int | None = None,
) -> None:
    logger.info(
        "Token refresh decision account_id=%s source=%s decision=%s next_allowed_at=%s failure_count=%s",
        account_id,
        source.value,
        decision,
        next_allowed_at,
        failure_count,
    )
