## Context

Save-time proxy validation (`account_proxy_probe.py`) constructs a one-shot `ProxyConnector` from **proposed** proxy fields and runs an OAuth refresh probe. It does not record the observed public IP and does not exercise the **persisted** per-account HTTP client registry used by runtime traffic.

Egress verification closes that gap by probing through `lease_account_http_client(account_id)` and persisting the observed globally routable public IP for reporting and optional guardrails.

## Goals / Non-Goals

**Goals**

- Record last observed globally routable public IP per account via the runtime account-bound client path.
- Fleet report with stored status (`unknown` / `ok` / `probe_failed`) and computed primary status with fixed precedence.
- Warnings list for cross-cutting risks (`local_dns_risk`) without overloading primary status.
- Dashboard UI with probe-now action and warnings.
- Configurable guardrail mode; `block` filters unsafe **selectable** accounts in load balancer selection.

**Non-Goals**

- Automatic periodic background probing (manual/on-demand only in v1).
- Replacing save-time proxy validation.
- Storing `shared_egress` as a DB column (derived at report time).

## Decisions

1. **Separate probe module** (`account_egress_probe.py`) — avoids conflating save-time OAuth refresh probes with IP discovery.
2. **Stored probe status is minimal** (`unknown`, `ok`, `probe_failed`); report layer computes a single primary status.
3. **Primary status precedence** — `probe_failed` > `shared_egress` > `direct_egress` > `ok` > `unknown`.
4. **`local_dns_risk` is a warning**, not a primary status; may coexist with any primary status.
5. **Failed probes clear observed IP** — no stale IP in summary, report derivation, or guardrails.
6. **IP validation requires `ip.is_global`** — rejects RFC1918, loopback, documentation/test-net, and other non-global addresses.
7. **Report includes all accounts**; shared-IP grouping and guardrail blocking consider only report-eligible / selectable subsets respectively.
8. **Default guardrail `warn`** — never blocks until operator opts into `block`.
9. **Never block on `unknown` alone** — fresh installs remain routable before first probe.
10. **Block filter location** — `load_balancer._load_selection_inputs` after `_selectable_accounts`, not `balancer/logic.py`.
11. **Selection cache invalidation** — `probe_account_egress` must call `get_account_selection_cache().invalidate()` after persisting egress fields so `block` mode cannot use stale cached eligibility.
12. **Dashboard chip, not card** — the accounts dashboard should expose egress
    risk as compact chips in existing account surfaces. Do not add a new
    full-width card or nest a card inside the account detail panel for the
    summary state.

## Settings (normative defaults)

| Setting | Default |
|---------|---------|
| `account_egress_probe_enabled` | `true` |
| `account_egress_probe_url` | `https://api.ipify.org?format=json` |
| `account_egress_probe_timeout_seconds` | `8.0` |
| `account_egress_guardrail_mode` | `warn` |
| `account_egress_allow_direct_accounts` | `false` |
| `account_egress_allow_shared_observed_ip` | `false` |

## Risks / Trade-offs

- External IP check services add a runtime dependency → configurable URL and timeout; probe failures are non-fatal in `warn` mode.
- Shared-IP detection is best-effort on last observed IPs → stale probes may false-negative until re-probed.
- Account rows are already dense → the list uses only chip-level egress summary
  while the detail section carries observed IP, checked time, probe error, and
  proxy endpoint details.

## Dashboard Presentation

Composer should implement a small reusable egress chip mapper for the accounts
frontend, then use it in both `AccountListItem` and `AccountProxySection`.

Canonical primary chip labels:

| Primary status | Label |
|----------------|-------|
| `ok` | `Egress OK` |
| `unknown` or missing egress | `Egress unknown` |
| `direct_egress` | `Direct egress` |
| `shared_egress` | `Shared IP` |
| `probe_failed` | `Probe failed` |

Warning chip labels:

| Warning | Label |
|---------|-------|
| `local_dns_risk` | `Local DNS risk` |

Severity mapping:

- `ok`: safe/green treatment.
- `unknown`: neutral/gray outline treatment.
- `direct_egress`: warning/amber treatment.
- `shared_egress`: critical/red treatment.
- `probe_failed`: critical/red treatment.
- `local_dns_risk`: warning/amber secondary chip.

Account list guidance:

- Show the primary egress chip in the existing account list row, near the
  account status badge or metadata row.
- Show at most the compact warning chips needed to flag risk; do not render the
  long explanatory warning text in the list.
- Do not make the list chip an interactive nested control because the account
  list item is already a button.
- The chip row must wrap cleanly on narrow widths without hiding account status
  or quota rows.

Account detail guidance:

- The `Network egress` section should show the same primary chip and warning
  chips above the observed IP / checked-at / error details.
- Keep `Verify egress`, proxy edit, and remove proxy actions in the section
  header.
- Long warning copy is allowed only in the detail section or tooltip, not in
  the list row.
- Failed probes must show `Probe failed` and error text, but must not show stale
  observed IP.

Accessibility:

- Chip text must carry the status; color is supplementary.
- Each chip should expose a useful `title` or tooltip/accessible label that
  includes the status meaning and, when available, observed IP and checked time.

## Migration Plan

1. Alembic adds nullable egress columns with defaults (`egress_last_probe_status='unknown'`).
2. Deploy backend + frontend; operators run manual probes.
3. Optionally enable `account_egress_guardrail_mode=block` after verification.

## Open Questions

(none)
