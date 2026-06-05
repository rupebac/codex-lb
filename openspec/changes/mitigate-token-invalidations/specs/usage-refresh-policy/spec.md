## ADDED Requirements

### Requirement: app_session_terminated at the refresh boundary deactivates the account

The system MUST treat OAuth refresh endpoint failures with error code
`app_session_terminated` as permanent authentication failures. The affected
account MUST be deactivated and removed from the routing pool until it is
re-authenticated.

#### Scenario: Refresh-time app_session_terminated is classified as permanent
- **WHEN** `classify_refresh_error("app_session_terminated")` is evaluated
- **THEN** it returns `True`

#### Scenario: Refresh-time app_session_terminated deactivates the account
- **WHEN** `AuthManager.refresh_account` receives a
  `RefreshError("app_session_terminated", ..., is_permanent=True)` from
  `refresh_access_token`
- **THEN** the account is transitioned to `DEACTIVATED`
- **AND** the deactivation reason references the re-login requirement so the
  dashboard can surface it
- **AND** the account is no longer selected by the load balancer until it is
  re-authenticated

#### Scenario: Usage-refresh-time app_session_terminated deactivates the account
- **WHEN** background usage refresh observes an upstream error whose code is
  `app_session_terminated`
- **THEN** the account is transitioned to `DEACTIVATED` immediately, without
  entering the ambiguous-401 cooldown loop

### Requirement: Background usage refresh is staggered across accounts

Background usage refresh MUST default to a 120 second refresh interval and MUST
spread account refresh attempts across that interval instead of refreshing all
accounts in one burst. For a cycle with `N` non-deactivated accounts, the
scheduler MUST attempt at most one account per slice of
`usage_refresh_interval_seconds / N` seconds, preserving each account's
configured direct or SOCKS5 egress path.

Manual or explicitly scoped usage refresh calls MAY continue to refresh the
provided account list immediately.

#### Scenario: Accounts are split evenly across the refresh window
- **GIVEN** `usage_refresh_interval_seconds=120`
- **AND** there are four non-deactivated accounts
- **WHEN** the background usage scheduler runs
- **THEN** it attempts one account every 30 seconds
- **AND** each account is attempted once per 120 second cycle

#### Scenario: Deactivated accounts are excluded from the scheduler window
- **GIVEN** one account is deactivated
- **WHEN** the background usage scheduler computes its refresh slices
- **THEN** the deactivated account does not consume a slice
- **AND** no usage fetch is attempted for that account
