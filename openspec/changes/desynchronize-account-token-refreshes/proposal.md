## Why

Token refresh jitter currently changes when an account becomes eligible for
OAuth refresh, but it does not control when refresh attempts actually start.
After startup, quiet periods, quota probes, or usage-refresh 401 retries, many
accounts can still enter `AuthManager.ensure_fresh(..., force=True)` in a tight
sequence from the same service. That creates a correlated OAuth pattern even
when normal proxy traffic is low.

The account-protection goal is to make OAuth refresh behavior look like a set of
independent clients: each account has its own durable next-refresh schedule,
background refresh starts are paced globally, transient failures back off, and
inactive/quota-exceeded accounts do not create unnecessary OAuth traffic.

## What Changes

- Persist per-account OAuth refresh scheduling metadata on `accounts`.
- Add a process-local token-refresh pacer for background/proactive refreshes
  with low default concurrency and minimum spacing between refresh starts.
- Keep live request refreshes usable: request-path refreshes may bypass
  background spacing when required to serve traffic, while still using
  singleflight and existing token-refresh admission.
- Treat usage-refresh forced refreshes as background repairs unless they are
  directly attached to a live proxied request.
- Skip proactive/background refresh for deactivated, paused,
  reauth-required, or quota-exceeded accounts unless an explicit live request
  requires it.
- Record refresh attempt/result metadata so retries, backoff, and future
  scheduling survive process restarts.
- Add focused tests proving burst prevention, force semantics, skip policy,
  migration compatibility, and observability.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `outbound-http-clients`: define durable token-refresh scheduling, pacing,
  admission, backoff, and live-request bypass behavior for OAuth refresh calls.
- `usage-refresh-policy`: require background usage refresh auth repairs to
  respect the token-refresh scheduler instead of forcing clustered OAuth calls.

## Impact

- Database: new nullable/defaulted columns on `accounts` for token refresh
  schedule/attempt metadata.
- Backend: `AuthManager`, account repository ports/implementations, settings,
  migration, and usage refresh auth-repair path.
- Existing transport identity work remains unchanged: refreshed OAuth calls
  still use the Codex CLI-compatible user agent/originator and per-account
  egress session.
- Existing per-account deterministic jitter remains useful as the base
  eligibility window; this change adds execution pacing and persistence.
