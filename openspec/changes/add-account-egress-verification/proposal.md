## Why

Per-account proxy configuration proves SOCKS5 connectivity at save time, but operators still lack visibility into the **effective public egress IP** each account uses at runtime. Multiple accounts can share the same direct egress IP or collide on a proxy, and local DNS resolution (`proxy_remote_dns=false`) can leak hostname lookups outside the proxy path. Operators need verification, reporting, and optional guardrails that measure egress through the same account-bound HTTP client used for real traffic.

## What Changes

- Add persisted egress probe results on each account (`egress_last_observed_ip`, timestamps, probe status/error).
- Add an account-bound egress probe module that uses `lease_account_http_client(account_id)` (not the save-time proxy probe).
- Add dashboard API endpoints to probe one account and report fleet-wide egress status with computed primary status (precedence: `probe_failed` > `shared_egress` > `direct_egress` > `ok` > `unknown`) and warnings (`local_dns_risk`).
- Surface egress status inline on `AccountSummary` and in the accounts UI; failed probes clear stored observed IP (no stale values).
- Add normative settings: `account_egress_probe_enabled`, `account_egress_probe_url`, `account_egress_probe_timeout_seconds`, `account_egress_guardrail_mode`, `account_egress_allow_direct_accounts`, `account_egress_allow_shared_observed_ip`.
- Add configurable guardrail mode (`off` / `warn` / `block`) with load-balancer filtering in `block` mode for selectable accounts only.
- Require globally routable IPs (`ip.is_global`) from probe responses; reject RFC1918 and documentation/test-net addresses.
- Alembic migration for new account columns.

## Capabilities

### New Capabilities

(none — extends existing account egress capability)

### Modified Capabilities

- `account-egress-proxy`: Add egress verification/reporting requirements distinct from save-time proxy validation; dashboard API and guardrail behavior.
- `outbound-http-clients`: Require egress probes to use the persisted account-bound HTTP client path.
- `proxy-admission-control`: When guardrail mode is `block`, exclude unsafe accounts during load-balancer selection.

## Impact

- Database: new nullable columns on `accounts`.
- Backend: `app/core/clients/account_egress_probe.py`, accounts repository/service/API, settings, optional load-balancer filter.
- Frontend: accounts schemas, API client, hooks, proxy/egress UI section.
- Tests: repository, probe unit, API integration, load-balancer (block mode), frontend schema/component tests.
