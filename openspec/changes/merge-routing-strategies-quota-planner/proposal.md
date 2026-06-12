## Why

PR 875 introduced account routing strategies, routing policies, API-key traffic classes, and quota-planner cost hints that can reduce unnecessary simultaneous account burn. The manual merge must preserve those behaviors while keeping the existing account egress isolation and Codex identity work intact.

## What Changes

- Expose and honor the full routing strategy set through dashboard settings and proxy selection.
- Persist API-key traffic classes and route opportunistic keys through opportunistic account admission.
- Feed quota-planner settings into the live proxy repository bundle so request-scoped routing costs can influence account selection.
- Keep quota-planner background scheduling opt-in to avoid extra background DB/account activity unless the operator enables it.
- Keep single-account routing scoped to the configured account ID while preserving API-key account assignment limits.

## Impact

- Operators can drain or preserve accounts more deliberately instead of spreading traffic across all accounts by accident.
- Opportunistic API keys can be constrained to expendable capacity.
- Planner costs can nudge routing without bypassing hard eligibility, health, quota, or sticky-continuity gates.
- The planner scheduler does not run by default, so the merge does not add a new periodic background account-management loop.
