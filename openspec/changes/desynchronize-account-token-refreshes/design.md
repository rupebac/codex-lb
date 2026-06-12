## Current Behavior

Relevant code paths:

- `app/core/auth/refresh.py`
  - `should_refresh(last_refresh, account_id=...)` applies a deterministic
    early-refresh offset.
  - `refresh_access_token(...)` performs the OAuth POST using
    `lease_account_http_session(...)`.
- `app/modules/accounts/auth_manager.py`
  - `AuthManager.ensure_fresh(account, force=False)` calls
    `_REFRESH_SINGLEFLIGHT.run(...)` when `force=True` or `should_refresh(...)`
    returns true.
  - `AuthManager.refresh_account(...)` writes rotated tokens and `last_refresh`
    after a successful refresh.
  - Request-path callers can pass `acquire_refresh_admission`, backed by
    `proxy_token_refresh_limit`.
- `app/modules/usage/updater.py`
  - `UsageUpdater.refresh_accounts(...)` walks accounts sequentially.
  - `_refresh_account(...)` calls `AuthManager.ensure_fresh(account, force=True)`
    after a usage fetch returns a retryable `401`.

The existing jitter only answers "is this token due?". It does not answer "may
this process start an OAuth request right now?". If many accounts become due,
or if many stale accounts hit usage-refresh 401s, the current path can still
start many OAuth refreshes close together.

## Desired Model

Split OAuth refresh into three decisions:

1. Eligibility: `should_refresh(...)` and persisted schedule determine whether
   an account should be refreshed soon.
2. Admission: singleflight and token-refresh admission prevent duplicate or
   excessive concurrent refreshes.
3. Pacing: background/proactive refreshes wait for a global low-rate pacer so
   accounts do not refresh in a cluster.

Live request refresh is different from background refresh:

- A selected account with a live proxied request must be able to refresh when
  needed to serve the request.
- It must still use per-account singleflight and `proxy_token_refresh_limit`.
- It should update the same persisted schedule metadata on success/failure.
- It should not be delayed by the background minimum-spacing pacer.

Background refresh sources include usage refresh auth repair, auth guardian,
manual fleet refresh, warmups/probes that are not directly serving a client
request, and startup reconciliation.

## Data Model

Add nullable/defaulted columns to `accounts`:

- `token_refresh_next_allowed_at: datetime | None`
  - Earliest time a background/proactive refresh may start for this account.
- `token_refresh_last_attempt_at: datetime | None`
  - Last OAuth refresh attempt start time, successful or failed.
- `token_refresh_last_result: str | None`
  - One of `success`, `failure`, or `skipped`.
- `token_refresh_last_reason: str | None`
  - Source/reason such as `live_request`, `usage_refresh_401`,
    `auth_guardian`, `manual`, `warmup`, or `startup`.
- `token_refresh_failure_count: int`
  - Consecutive non-permanent refresh failures used for exponential backoff.

Migration guidance:

- Existing rows may leave `token_refresh_next_allowed_at` null.
- New code must lazily initialize null schedules without immediately refreshing
  every eligible account.
- `token_refresh_failure_count` should backfill to `0`.
- Do not rewrite encrypted token material.

## Settings

Add settings with conservative defaults:

- `account_token_refresh_background_concurrency: int = 1`
  - Maximum number of background/proactive OAuth refreshes in flight per
    process.
- `account_token_refresh_min_start_spacing_seconds: float = 300.0`
  - Minimum process-local time between background/proactive OAuth refresh
    starts.
- `account_token_refresh_initial_spread_hours: float = 24.0`
  - Window used to lazily distribute existing/null schedules across accounts.
- `account_token_refresh_failure_backoff_base_seconds: float = 300.0`
  - Base delay after transient refresh failure.
- `account_token_refresh_failure_backoff_max_seconds: float = 3600.0`
  - Maximum transient failure backoff.
- `account_token_refresh_background_refresh_quota_exceeded: bool = False`
  - When false, background/proactive paths skip quota-exceeded accounts unless
    a live request forces the refresh.

Keep existing settings:

- `token_refresh_interval_days`
- `account_token_refresh_jitter_hours`
- `proxy_token_refresh_limit`
- `usage_refresh_auth_failure_cooldown_seconds`

## Scheduling Rules

Suggested helper shape:

```python
class TokenRefreshSource(StrEnum):
    LIVE_REQUEST = "live_request"
    USAGE_REFRESH_401 = "usage_refresh_401"
    AUTH_GUARDIAN = "auth_guardian"
    MANUAL = "manual"
    WARMUP = "warmup"
    STARTUP = "startup"

@dataclass(frozen=True)
class TokenRefreshDecision:
    allowed: bool
    reason: str
    next_allowed_at: datetime | None
    bypass_background_pacer: bool = False
```

Implementation may use a different shape, but it must preserve these semantics.

Background/proactive scheduler logic:

1. Exclude deactivated, paused, and reauth-required accounts before checking
   OAuth state.
2. Exclude quota-exceeded accounts when
   `account_token_refresh_background_refresh_quota_exceeded=false`, unless the
   caller marks the source as `live_request`.
3. If `token_refresh_next_allowed_at` is null, initialize it to a stable time
   derived from account id inside `account_token_refresh_initial_spread_hours`.
   Persist the initialized value and do not refresh the account in that same
   scheduler tick unless the initialized value is already due.
4. Only attempt OAuth refresh when both:
   - `should_refresh(last_refresh, account_id=account.id)` is true, and
   - `token_refresh_next_allowed_at <= now`.
5. Acquire the background pacer before starting OAuth refresh:
   - enforce `account_token_refresh_background_concurrency`,
   - enforce `account_token_refresh_min_start_spacing_seconds` between starts.
6. On success:
   - reset `token_refresh_failure_count` to `0`,
   - set `token_refresh_last_result=success`,
   - set `token_refresh_last_reason` to the source,
   - set `token_refresh_last_attempt_at` to attempt start time,
   - set `token_refresh_next_allowed_at` to the next jittered eligibility point
     based on the new `last_refresh`.
7. On transient failure:
   - increment `token_refresh_failure_count`,
   - set `token_refresh_last_result=failure`,
   - set `token_refresh_last_reason` to the source,
   - set `token_refresh_last_attempt_at` to attempt start time,
   - set `token_refresh_next_allowed_at = now + exponential_backoff + stable
     per-account jitter`, capped by
     `account_token_refresh_failure_backoff_max_seconds`.
8. On permanent failure:
   - preserve existing deactivation behavior,
   - write attempt/result metadata before or with the status update.

Live request logic:

1. `AuthManager.ensure_fresh(...)` needs source/context, for example
   `source=TokenRefreshSource.LIVE_REQUEST`.
2. Live request refresh may bypass `token_refresh_next_allowed_at` and the
   background pacer when the account is already selected for a request.
3. Live request refresh must still use `_REFRESH_SINGLEFLIGHT` and
   `proxy_token_refresh_limit` admission.
4. Concurrent live requests for the same account must join the same
   singleflight refresh.
5. Live request success/failure must update the same persisted schedule fields.

Usage refresh auth repair:

- The `UsageUpdater._refresh_account(...)` retry path after usage `401` must
  call `AuthManager.ensure_fresh(...)` with a background source such as
  `USAGE_REFRESH_401`, not with live-request bypass semantics.
- If the token scheduler denies or delays the background refresh, usage refresh
  should mark the account as not written/not succeeded and allow the next usage
  cycle to retry after the schedule/cooldown.
- Usage refresh must not deactivate or mark an account unhealthy merely because
  the token-refresh scheduler deferred the OAuth attempt.

## Observability

Add structured logs for each scheduler decision:

- `account_id`
- refresh source
- decision (`not_due`, `scheduled`, `started`, `success`, `transient_failure`,
  `permanent_failure`, `skipped_status`, `skipped_quota`, `deferred_pacer`)
- `next_allowed_at`
- `failure_count`

The account API may expose schedule metadata later, but it is not required for
this change unless Composer needs it for tests. Repository-level tests are
enough for the durable contract.

## Test Strategy

Use fake clocks / monkeypatched sleeps for pacing tests. Do not use real
network calls.

High-value tests:

- Unit: null schedules are initialized across the spread window and do not all
  refresh immediately.
- Unit: background refreshes respect concurrency `1` and min start spacing.
- Unit: live request refresh bypasses background spacing but still uses
  singleflight/admission.
- Unit: usage-refresh `401` repair is treated as background and can be deferred.
- Unit: quota-exceeded, deactivated, paused, and reauth-required accounts are
  skipped for background refresh.
- Unit: transient failures back off and permanent failures still deactivate.
- Integration: Alembic upgrade works on existing account rows and fresh DB.
- Regression: existing `should_refresh(...)` deterministic jitter tests still
  pass.
