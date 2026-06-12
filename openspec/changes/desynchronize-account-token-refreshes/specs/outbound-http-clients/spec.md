## ADDED Requirements

### Requirement: Background OAuth token refresh starts are paced

The system MUST distinguish token refresh eligibility from token refresh
execution. A background or proactive OAuth token refresh MUST NOT start merely
because `should_refresh(...)` returns true; it MUST also pass the persisted
per-account schedule and the process-local background refresh pacer.

The background refresh pacer MUST enforce
`account_token_refresh_background_concurrency` and
`account_token_refresh_min_start_spacing_seconds` for background/proactive
OAuth refresh starts. The default concurrency MUST be `1`, and the default
minimum start spacing MUST be at least `300` seconds.

Live proxied requests MAY bypass the background pacer when the selected account
requires refresh to serve that request, but they MUST still use per-account
singleflight and `proxy_token_refresh_limit` admission.

#### Scenario: Due background refreshes do not start in one burst
- **GIVEN** three active accounts whose tokens are refresh-eligible
- **AND** all three accounts have `token_refresh_next_allowed_at` in the past
- **AND** `account_token_refresh_background_concurrency=1`
- **AND** `account_token_refresh_min_start_spacing_seconds=300`
- **WHEN** a background refresh runner processes the accounts
- **THEN** no more than one OAuth refresh is in flight at a time
- **AND** the second and third OAuth refresh starts are each separated by at
  least 300 seconds from the previous background OAuth refresh start

#### Scenario: Live request refresh bypasses background spacing
- **GIVEN** an account selected for a live proxied request
- **AND** the account needs token refresh before the request can be sent
- **AND** a background refresh started less than
  `account_token_refresh_min_start_spacing_seconds` ago
- **WHEN** the live request calls `AuthManager.ensure_fresh` with live-request
  semantics
- **THEN** the refresh MAY start without waiting for the background spacing
  window
- **AND** it MUST still acquire `proxy_token_refresh_limit` admission when that
  admission hook is configured
- **AND** concurrent live requests for the same account MUST share one
  singleflight refresh

### Requirement: Token refresh schedule is persisted per account

Each account MUST persist token refresh schedule and attempt metadata so refresh
distribution survives process restarts. The persisted metadata MUST include, at
minimum:

- `token_refresh_next_allowed_at`
- `token_refresh_last_attempt_at`
- `token_refresh_last_result`
- `token_refresh_last_reason`
- `token_refresh_failure_count`

When `token_refresh_next_allowed_at` is null, background/proactive refresh code
MUST lazily initialize it to a stable account-specific time inside
`account_token_refresh_initial_spread_hours`. Lazy initialization MUST persist
the value and MUST NOT refresh every null-schedule account in the same scheduler
tick unless each initialized time is already due.

After a successful OAuth refresh, the system MUST reset
`token_refresh_failure_count` to `0`, record success metadata, and set the next
allowed background refresh time from the new `last_refresh` plus the configured
token interval and per-account jitter. The configured
`token_refresh_interval_days` MUST remain the hard maximum eligibility age; if
an account is already past that maximum, it MUST be scheduled into the earliest
available paced background slot, while live requests may refresh immediately.

#### Scenario: Existing accounts are not refreshed immediately after migration
- **GIVEN** multiple historical account rows have null
  `token_refresh_next_allowed_at`
- **WHEN** background token refresh scans those accounts after upgrade
- **THEN** it initializes stable per-account `token_refresh_next_allowed_at`
  values across `account_token_refresh_initial_spread_hours`
- **AND** it does not start OAuth refresh for every initialized account in the
  same scheduler tick

#### Scenario: Successful refresh schedules the next background opportunity
- **WHEN** an OAuth token refresh succeeds for an account
- **THEN** the account's refresh schedule metadata records
  `token_refresh_last_result=success`
- **AND** `token_refresh_failure_count` is reset to `0`
- **AND** `token_refresh_next_allowed_at` is moved to the next account-specific
  refresh opportunity

### Requirement: Token refresh failures back off without retry storms

Transient OAuth refresh failures MUST update per-account refresh metadata and
delay the next background/proactive refresh attempt with exponential backoff.
The delay MUST use `account_token_refresh_failure_backoff_base_seconds`, MUST be
capped by `account_token_refresh_failure_backoff_max_seconds`, and MUST include
a stable per-account jitter component so repeated failures do not re-cluster.

Permanent OAuth refresh failures MUST preserve the existing deactivation
behavior and MUST record refresh attempt metadata before or with the status
transition.

#### Scenario: Transient refresh failure schedules backoff
- **WHEN** OAuth token refresh for an account fails with a transient transport
  error
- **THEN** `token_refresh_failure_count` increases
- **AND** `token_refresh_last_result` records `failure`
- **AND** `token_refresh_next_allowed_at` is set to a future backoff time
- **AND** background refresh MUST skip the account until that time is due

#### Scenario: Permanent refresh failure still deactivates
- **WHEN** OAuth token refresh fails with a permanent refresh-token error
- **THEN** the account is transitioned to `DEACTIVATED`
- **AND** the refresh attempt metadata records the permanent failure source
- **AND** the account is removed from selection as before

### Requirement: Background refresh skips accounts that should not create OAuth traffic

Background/proactive token refresh MUST skip accounts that are not selectable
or should not create background OAuth traffic. At minimum, it MUST skip
deactivated, paused, and reauth-required accounts. It MUST also skip
quota-exceeded accounts unless
`account_token_refresh_background_refresh_quota_exceeded=true` or the refresh is
required for a live proxied request.

A scheduler skip MUST NOT deactivate the account and MUST NOT mark the account
unhealthy. It MAY record `token_refresh_last_result=skipped` and a reason for
operator visibility.

#### Scenario: Quota-exceeded account is not proactively refreshed
- **GIVEN** an active account is quota-exceeded
- **AND** `account_token_refresh_background_refresh_quota_exceeded=false`
- **WHEN** a background refresh runner scans the account
- **THEN** no OAuth refresh is attempted for that account
- **AND** the account is not deactivated because of the skip

#### Scenario: Live request may refresh a skipped background account
- **GIVEN** an account would be skipped by background refresh policy
- **AND** the account is selected for a live proxied request that requires a
  token refresh
- **WHEN** live-request refresh is invoked
- **THEN** the refresh MAY proceed through live-request semantics
- **AND** the result MUST update the same refresh schedule metadata
