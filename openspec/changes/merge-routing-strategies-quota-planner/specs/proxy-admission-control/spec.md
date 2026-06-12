## ADDED Requirements

### Requirement: Account routing settings reach live proxy selection

The proxy MUST honor every persisted dashboard routing strategy value supported by the account selector: `usage_weighted`, `round_robin`, `capacity_weighted`, `relative_availability`, `fill_first`, `sequential_drain`, `reset_drain`, and `single_account`. Unsupported stored values MUST fall back to `capacity_weighted`.

#### Scenario: Persisted drain strategies are not collapsed

- **WHEN** dashboard settings contain `fill_first`, `sequential_drain`, `reset_drain`, or `single_account`
- **THEN** live proxy account selection receives that same routing strategy

### Requirement: Single-account routing honors the configured account ID

When the persisted routing strategy is `single_account` and `single_account_id` is configured, live proxy account selection MUST scope eligible accounts to that account ID. If an API key is account-assignment scoped, the configured single account MUST also be inside that API-key scope; otherwise selection MUST fail closed with no account.

#### Scenario: Single account intersects API-key scope

- **GIVEN** routing strategy `single_account`
- **AND** `single_account_id = "acc_a"`
- **AND** an API key scoped to only `"acc_b"`
- **WHEN** the proxy selects an account for that API key
- **THEN** it does not route to `"acc_a"` or `"acc_b"`
- **AND** it reports no eligible account

### Requirement: Quota planner costs feed request routing

Live proxy selection MUST load quota-planner settings from the request repository bundle and pass request-scoped planner costs into account selection after hard eligibility and health filters. Missing or failing planner settings MUST fall back to default shadow settings without blocking proxy requests.

#### Scenario: Planner repository is available to live selection

- **WHEN** the application constructs proxy repositories for live request selection
- **THEN** the bundle includes quota-planner repository access
- **AND** request selection can build routing costs from persisted planner settings

### Requirement: Quota planner scheduler is opt-in

The quota-planner background scheduler MUST be disabled by default. Operators MAY enable it explicitly through configuration. Disabled scheduler construction MUST NOT create a periodic background task or open background database sessions.

#### Scenario: Default startup does not run planner ticks

- **WHEN** the application starts with no quota-planner scheduler override
- **THEN** the quota-planner scheduler is constructed disabled
- **AND** it does not run planner ticks in the background

### Requirement: Opportunistic traffic uses expendable account capacity

When a valid API key has `traffic_class = "opportunistic"`, live proxy selection MUST pass opportunistic traffic class to account selection. Opportunistic selection MUST retain existing model, quota, health, sticky, account-assignment, and local-concurrency gates.

#### Scenario: Opportunistic key selects through opportunistic admission

- **GIVEN** an authenticated API key with `traffic_class = "opportunistic"`
- **WHEN** the proxy selects an upstream account for a protected proxy request
- **THEN** it invokes account selection with opportunistic traffic class
