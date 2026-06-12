## ADDED Requirements

### Requirement: Usage refresh token repair MUST respect OAuth refresh pacing

Background usage refresh MUST invoke OAuth token refresh with background
refresh semantics when it receives a retryable auth-like response and needs to
repair an account token. Usage-refresh token repair MUST NOT use live-request
bypass semantics unless it is directly attached to an active proxied client
request.

If the token refresh scheduler defers the OAuth attempt because the account is
not due, is in backoff, is skipped by background policy, or is waiting on the
background pacer, usage refresh MUST treat the usage attempt as not succeeded
and MUST leave normal retry/cooldown behavior to later cycles. Scheduler
deferral MUST NOT deactivate the account, mark it unhealthy, or clear existing
tokens.

#### Scenario: Usage 401 repair is paced as background refresh
- **WHEN** background usage refresh receives a retryable `401` for an account
- **AND** the account token would require OAuth refresh before retrying usage
- **THEN** the OAuth refresh request uses background refresh semantics
- **AND** it is subject to the persisted account schedule and background pacer

#### Scenario: Deferred usage repair is not treated as account failure
- **GIVEN** background usage refresh needs token repair for an account
- **AND** the token refresh scheduler defers the OAuth attempt until a future
  `token_refresh_next_allowed_at`
- **WHEN** usage refresh handles that scheduler decision
- **THEN** the usage refresh result is not marked successful
- **AND** the account is not deactivated
- **AND** the account is not marked unhealthy
- **AND** a later usage refresh cycle may retry after the schedule permits it
