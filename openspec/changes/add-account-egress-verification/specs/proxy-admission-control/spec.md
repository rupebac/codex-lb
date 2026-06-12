## ADDED Requirements

### Requirement: Egress guardrails filter unsafe accounts during selection

When `account_egress_guardrail_mode` is `block`, the proxy load balancer MUST remove **selectable** accounts whose computed egress primary status is `direct_egress` or `shared_egress` (subject to `account_egress_allow_direct_accounts` and `account_egress_allow_shared_observed_ip`) from selection inputs after base selectability filtering and before model/quota filtering completes. Confirmed direct egress MUST be blocked by the direct-egress rule even when the account's computed primary status is `shared_egress` because a non-selectable report peer shares its IP.

Shared-IP comparisons for blocking MUST include only selectable accounts with stored `egress_last_probe_status=ok` and non-null `egress_last_observed_ip`. Non-selectable accounts (paused, deactivated, etc.) MUST NOT participate in shared-IP blocking decisions.

Accounts with stored probe status `unknown` MUST remain eligible. Accounts blocked solely due to `warnings` containing `local_dns_risk` MUST remain eligible.

#### Scenario: Unknown egress does not block routing
- **GIVEN** `account_egress_guardrail_mode=block`
- **WHEN** a selectable account has never been egress-probed (`egress_last_probe_status=unknown`)
- **THEN** that account remains eligible for load-balancer selection

#### Scenario: Shared IP selectable accounts blocked when disallowed
- **GIVEN** `account_egress_guardrail_mode=block` and `account_egress_allow_shared_observed_ip=false`
- **WHEN** two selectable accounts share the same confirmed observed globally routable IP
- **THEN** both accounts are excluded from selection inputs

#### Scenario: Deactivated peer does not block selectable account
- **GIVEN** `account_egress_guardrail_mode=block` and `account_egress_allow_shared_observed_ip=false`
- **AND** the selectable active account has a configured proxy
- **WHEN** the selectable active account shares an observed IP only with a deactivated account
- **THEN** the active account is NOT excluded for `shared_egress`
- **AND** the direct-egress block rule does not apply because the active account has a configured proxy
