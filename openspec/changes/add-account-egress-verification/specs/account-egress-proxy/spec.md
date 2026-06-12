## ADDED Requirements

### Requirement: Egress verification is distinct from save-time proxy validation

The service MUST provide account egress verification that records the effective globally routable public IP observed through the persisted account-bound HTTP client path. This verification MUST NOT reuse the save-time SOCKS5 proxy probe. Save-time validation proves proxy connectivity to upstream OAuth; egress verification proves the public IP of the runtime account egress path.

Stored probe status on the account row MUST be one of: `unknown`, `ok`, `probe_failed`. Report-level **primary** status MUST be computed from stored state using the precedence rule in the computed-status requirement below. `local_dns_risk` MUST NOT be a primary status; it MUST appear only in the `warnings` list.

#### Scenario: Egress probe uses the persisted account client
- **WHEN** an operator triggers egress verification for an account
- **THEN** the probe MUST acquire an HTTP client via the account-bound egress lease helper for that `account_id`
- **AND** MUST NOT use the global shared outbound client
- **AND** MUST NOT use the one-shot save-time proxy session builder

#### Scenario: Successful probe persists observed IP
- **WHEN** the egress probe receives a globally routable public IP from the configured probe URL
- **THEN** the service persists `egress_last_observed_ip`, `egress_last_observed_at`, `egress_last_checked_at`, `egress_last_probe_status=ok`, and clears `egress_last_probe_error`

#### Scenario: Failed probe clears prior observed IP
- **WHEN** the egress probe cannot obtain a valid globally routable public IP
- **THEN** the service persists `egress_last_checked_at`, `egress_last_probe_status=probe_failed`, and `egress_last_probe_error`
- **AND** MUST set `egress_last_observed_ip` and `egress_last_observed_at` to `NULL`
- **AND** MUST NOT treat the account as having a confirmed egress IP
- **AND** MUST NOT use any previously stored IP for shared/direct derivation or guardrail blocking

#### Scenario: Egress path changes reset stored probe state
- **WHEN** an account's proxy configuration is set, replaced, cleared, imported with proxy fields, or re-authenticated with proxy fields
- **THEN** the service MUST reset `egress_last_observed_ip`, `egress_last_observed_at`, `egress_last_checked_at`, and `egress_last_probe_error` to `NULL`
- **AND** MUST set `egress_last_probe_status=unknown`
- **AND** MUST invalidate load-balancer selection caches

### Requirement: Egress probe settings

The service MUST expose the following configuration settings with these exact names and defaults:

| Setting | Type | Default |
|---------|------|---------|
| `account_egress_probe_enabled` | bool | `true` |
| `account_egress_probe_url` | string | `https://api.ipify.org?format=json` |
| `account_egress_probe_timeout_seconds` | float (> 0) | `8.0` |
| `account_egress_guardrail_mode` | `off` \| `warn` \| `block` | `warn` |
| `account_egress_allow_direct_accounts` | bool | `false` |
| `account_egress_allow_shared_observed_ip` | bool | `false` |

When `account_egress_probe_enabled=false`, probe requests MUST respond HTTP `422` with `error.code=egress_probe_disabled` and MUST NOT mutate stored egress fields.

Environment variables MUST follow the project's existing settings naming convention (uppercase with underscores derived from the setting names above).

#### Scenario: Probe disabled rejects probe requests
- **GIVEN** `account_egress_probe_enabled=false`
- **WHEN** an operator POSTs to `/api/accounts/{account_id}/egress/probe`
- **THEN** the API responds HTTP `422` with `error.code=egress_probe_disabled`
- **AND** stored egress fields on the account are unchanged

### Requirement: Egress probe response parsing

The egress probe MUST support JSON responses containing an `ip` field and plain-text responses containing a single IP address. Parsed values MUST be validated with `ipaddress.ip_address` and MUST satisfy `ip.is_global` (globally routable; RFC1918, loopback, link-local, multicast, reserved, and documentation/test-net addresses MUST be rejected). Invalid, non-global, or missing values MUST classify as `probe_failed`.

#### Scenario: JSON ipify-style response with global IP
- **WHEN** the probe URL returns `{"ip":"93.184.216.34"}`
- **THEN** the probe records `93.184.216.34` as the observed IP

#### Scenario: Plain-text global IP response
- **WHEN** the probe URL returns body `8.8.8.8`
- **THEN** the probe records `8.8.8.8` as the observed IP

#### Scenario: Reserved documentation IP is rejected
- **WHEN** the probe URL returns `{"ip":"203.0.113.10"}`
- **THEN** the probe classifies the outcome as `probe_failed`
- **AND** does not persist `203.0.113.10` as the observed IP

#### Scenario: Private RFC1918 IP is rejected
- **WHEN** the probe URL returns `{"ip":"10.0.0.1"}`
- **THEN** the probe classifies the outcome as `probe_failed`

### Requirement: Computed report status precedence

Each account's report-level **primary** `status` MUST be computed from stored probe state and fleet-wide IP grouping using exactly one value, chosen by this precedence (highest wins):

1. `probe_failed` — stored `egress_last_probe_status=probe_failed`
2. `shared_egress` — stored status is `ok`, `egress_last_observed_ip` is non-null, and at least one other **report-eligible** account (see fleet report scope) has the same IP with stored status `ok`
3. `direct_egress` — stored status is `ok`, no proxy configured (`proxy_host IS NULL`), and primary status is not already `shared_egress`
4. `ok` — stored status is `ok` and none of the above apply
5. `unknown` — stored `egress_last_probe_status=unknown` or no successful probe has been recorded

`local_dns_risk` MUST NOT appear as the primary `status`. When a proxy is configured with `proxy_remote_dns=false`, the service MUST append the string `local_dns_risk` to the account's `warnings` list regardless of primary status.

Primary status and warnings MUST be independent: an account MAY have primary status `shared_egress` and warnings `["local_dns_risk"]` simultaneously.

#### Scenario: Shared egress takes precedence over direct egress
- **GIVEN** two report-eligible accounts with no proxy, stored status `ok`, and the same `egress_last_observed_ip`
- **WHEN** the fleet report is computed
- **THEN** both accounts have primary status `shared_egress`, not `direct_egress`

#### Scenario: Local DNS risk is a warning only
- **GIVEN** an account with a configured proxy and `proxy_remote_dns=false` and stored status `ok`
- **WHEN** the fleet report is computed
- **THEN** the account's primary status reflects probe/egress state (`ok`, `direct_egress`, or `shared_egress` as applicable)
- **AND** `warnings` includes `local_dns_risk`

### Requirement: Fleet egress report scope and shared-IP grouping

`GET /api/accounts/egress` MUST return one `AccountEgressStatus` entry for **every** account row regardless of `status` (active, paused, deactivated, etc.).

Shared-IP grouping for `shared_egress` and `shared_with_account_ids` MUST consider all **report-eligible** accounts regardless of operational status (active, paused, or deactivated). An account is report-eligible when stored `egress_last_probe_status=ok` and `egress_last_observed_ip` is non-null.

Guardrail blocking (see guardrail requirement) MUST apply only to accounts that are already selectable for load-balancer routing; non-selectable accounts MUST NOT affect whether selectable peers are blocked, even when they share an observed IP in the fleet report.

#### Scenario: Deactivated report-eligible account participates in shared grouping but not guardrail blocking
- **GIVEN** an active account and a deactivated account both report-eligible with the same observed IP
- **WHEN** the fleet report is computed
- **THEN** both accounts appear in the report
- **AND** both accounts have primary status `shared_egress`
- **AND** each lists the other account id in `shared_with_account_ids`
- **WHEN** load-balancer selection inputs are built with `account_egress_guardrail_mode=block`
- **THEN** the active account is NOT blocked for `shared_egress` solely because the deactivated peer shares the IP
- **AND** the deactivated account is not selectable regardless of egress status

#### Scenario: Report lists all accounts
- **GIVEN** accounts in mixed statuses (active, paused, deactivated)
- **WHEN** an operator GETs `/api/accounts/egress`
- **THEN** the response includes every account exactly once

### Requirement: Dashboard egress API

The dashboard API MUST expose:

- `POST /api/accounts/{account_id}/egress/probe` — run probe, persist result, return `AccountEgressStatus`
- `GET /api/accounts/egress` — return `AccountEgressReportResponse` for all accounts (see fleet report scope)

`AccountEgressStatus` MUST include: `status` (primary, per precedence above), `observed_ip`, `checked_at`, `error`, `configured_proxy`, `proxy_remote_dns`, `shared_with_account_ids`, and `warnings`. `checked_at` MUST reflect the most recent egress probe attempt, including failed probes whose `observed_ip` is `NULL`.

`AccountEgressReportResponse` MUST include:

- `accounts`: list of `AccountEgressStatus` (one per account row)
- `unknown_count`: count of accounts whose primary status is `unknown`
- `failed_count`: count of accounts whose primary status is `probe_failed`
- `direct_count`: count of accounts whose primary status is `direct_egress`
- `shared_ip_count`: count of accounts whose primary status is `shared_egress`

Summary counts MUST be derived from the computed primary status values in `accounts`, not from stored probe status alone.

`AccountSummary` read responses MUST include the latest egress status when the dashboard account list displays it inline. When stored status is `probe_failed`, inline summary MUST NOT expose a stale observed IP.

#### Scenario: Fleet report includes summary counts
- **GIVEN** a fleet with two `unknown`, one `probe_failed`, one `direct_egress`, and two `shared_egress` accounts
- **WHEN** an operator GETs `/api/accounts/egress`
- **THEN** the response includes `accounts` with six entries
- **AND** `unknown_count=2`, `failed_count=1`, `direct_count=1`, `shared_ip_count=2`

#### Scenario: Probe now returns current status
- **WHEN** an operator POSTs to `/api/accounts/{account_id}/egress/probe`
- **THEN** the response includes observed IP (if any), checked time, configured proxy flag, primary status, warnings, and `shared_with_account_ids`

### Requirement: Dashboard MUST present egress risk as compact chips

The dashboard MUST present account egress status as compact status chips in
existing account surfaces rather than as a separate dashboard card. The primary
egress chip MUST be rendered from `AccountSummary.egress` in the account list
row and in the account network-egress detail section. The account list MUST NOT
perform an additional per-account egress request to render the chip.

The primary chip label MUST use this mapping:

| Status | Label |
|--------|-------|
| `ok` | `Egress OK` |
| `unknown` or missing egress | `Egress unknown` |
| `direct_egress` | `Direct egress` |
| `shared_egress` | `Shared IP` |
| `probe_failed` | `Probe failed` |

Dashboard warning chips MUST use this mapping:

| Warning | Label |
|---------|-------|
| `local_dns_risk` | `Local DNS risk` |

The visual severity MUST be:

- `ok`: safe/green
- `unknown`: neutral/gray outline
- `direct_egress`: warning/amber
- `shared_egress`: critical/red
- `probe_failed`: critical/red
- `local_dns_risk`: warning/amber secondary chip

Chip text MUST carry the state without relying on color alone. Each chip MUST
provide an accessible label, `title`, or tooltip that explains the state; when
available, the explanation SHOULD include observed IP and checked time.

#### Scenario: Account list shows primary egress chip without extra fetches
- **GIVEN** `AccountSummary.egress.status=shared_egress`
- **AND** `AccountSummary.egress.warnings=["local_dns_risk"]`
- **WHEN** the account list row renders
- **THEN** it shows a primary chip labeled `Shared IP`
- **AND** it shows a warning chip labeled `Local DNS risk`
- **AND** it does not issue a separate egress report or probe request for that
  row
- **AND** the chips are not nested interactive controls inside the row button

#### Scenario: Missing egress summary falls back to unknown chip
- **GIVEN** an account summary has no `egress` object
- **WHEN** the account list row renders
- **THEN** it shows a primary chip labeled `Egress unknown`
- **AND** it does not show observed IP text

#### Scenario: Detail section reuses chip semantics and keeps details visible
- **GIVEN** an account has `egress.status=direct_egress`
- **AND** `egress.observed_ip=93.184.216.34`
- **AND** `egress.checked_at` is present
- **WHEN** the network-egress detail section renders
- **THEN** it shows the primary chip labeled `Direct egress`
- **AND** it shows the observed IP and checked time as detail text
- **AND** it keeps the `Verify egress` action available

#### Scenario: Failed probe chip does not show stale observed IP
- **GIVEN** an account has `egress.status=probe_failed`
- **AND** `egress.observed_ip` is null
- **AND** `egress.error` is present
- **WHEN** the account list and network-egress detail section render
- **THEN** both surfaces show a primary chip labeled `Probe failed`
- **AND** neither surface shows stale observed IP text
- **AND** the detail section shows the probe error

#### Scenario: Chips wrap without hiding account controls
- **GIVEN** a narrow dashboard viewport
- **AND** an account row contains account status, egress primary chip, and a
  `Local DNS risk` warning chip
- **WHEN** the row renders
- **THEN** the chips wrap or truncate within their container
- **AND** account status, quota rows, and selection behavior remain visible and
  usable

### Requirement: Egress guardrail mode

The service MUST honor `account_egress_guardrail_mode` (`off`, `warn`, `block`) and the allow flags defined in the settings requirement.

- `off` and `warn` MUST NOT filter accounts from load-balancer selection solely due to egress status.
- `block` MUST exclude **selectable** accounts whose computed primary status is `direct_egress` unless `account_egress_allow_direct_accounts=true`.
- `block` MUST exclude **selectable** accounts whose computed primary status is `shared_egress` unless `account_egress_allow_shared_observed_ip=true`.
- `block` MUST exclude **selectable** accounts with confirmed direct egress even when their computed primary status is `shared_egress` because a non-selectable report peer shares their IP.
- `block` MUST NOT exclude accounts solely because stored probe status is `unknown`.
- `block` MUST NOT exclude accounts solely because `warnings` contains `local_dns_risk`.

#### Scenario: Block mode removes direct egress accounts
- **GIVEN** `account_egress_guardrail_mode=block` and `account_egress_allow_direct_accounts=false`
- **WHEN** load-balancer selection inputs are built
- **THEN** selectable accounts with computed primary status `direct_egress` are not eligible for selection

#### Scenario: Non-selectable accounts do not trigger peer blocking
- **GIVEN** a deactivated account shares an observed IP with a selectable active account
- **AND** the selectable active account has a configured proxy
- **AND** `account_egress_guardrail_mode=block`
- **WHEN** load-balancer selection inputs are built
- **THEN** the active account is blocked for `shared_egress` only if another **selectable** account shares the same IP
- **AND** the direct-egress block rule does not apply because the active account has a configured proxy

### Requirement: Egress probe invalidates selection cache

After `probe_account_egress` persists egress probe fields (success or failure), the service MUST call `get_account_selection_cache().invalidate()` so subsequent load-balancer selection inputs reflect the updated egress eligibility. Guardrail `block` mode MUST NOT continue routing with stale cached selection inputs after a probe mutates egress state.

#### Scenario: Successful probe refreshes cached selection inputs
- **GIVEN** load-balancer selection inputs are cached
- **AND** `account_egress_guardrail_mode=block`
- **WHEN** an operator probe changes an account from `unknown` to `direct_egress`
- **THEN** the next load-balancer selection excludes that account without requiring process restart

#### Scenario: Failed probe refreshes cached selection inputs
- **GIVEN** load-balancer selection inputs are cached with an account excluded for `shared_egress`
- **WHEN** an operator probe for that account fails and clears its observed IP
- **THEN** the next load-balancer selection recomputes eligibility without the stale shared-egress exclusion
