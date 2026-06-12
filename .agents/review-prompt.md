# Code Review Request: Merge Routing Strategies + Quota Planner from PR 875

## Context

We maintain a Python/FastAPI load balancer proxy (`codex-lb`) that routes OpenAI API requests across multiple ChatGPT accounts. The project has two long-lived branches:

- **`feature/account-egress-isolation`** — The user's working branch with per-account SOCKS5 proxy support, account egress isolation, and a Codex CLI user-agent header system.
- **`pr-875`** (from Komzpa/codex-lb) — A large PR (~800 files changed) that added, among other things: 4 new routing strategies, routing policies, traffic classes, a quota planner module, an auth guardian, upstream proxy routing, workspace identity, and much more.

We wanted **only** the routing strategies and quota planner from PR 875, not the entire PR. This is a manual cherry-pick merge — we could not use `git merge` (too many unrelated changes) or `git cherry-pick` (changes interleaved across 120+ commits).

## What We Merged

### 1. Four New Routing Strategies (`app/core/balancer/logic.py`)

| Strategy | Behavior |
|---|---|
| `fill_first` | Deterministic — picks the account with highest primary usage %, deliberately draining the most saturated account first |
| `sequential_drain` | Drains accounts in order by capacity credits (highest first) |
| `reset_drain` | Drains based on reset window timing — accounts whose quota resets soonest get used first |
| `single_account` | Forces all traffic to a single account (lowest ID) |

The `RoutingStrategy` type expanded from 4 to 8 options:
```python
RoutingStrategy = Literal[
    "usage_weighted", "round_robin", "capacity_weighted", "relative_availability",
    "fill_first", "sequential_drain", "reset_drain", "single_account",
]
```

### 2. Routing Policies (`app/db/models.py`, `app/core/balancer/logic.py`)

Per-account routing policies that control how accounts are treated in the health pool:
- **`normal`** — Default behavior
- **`burn_first`** — Account is consumed first when expendable
- **`preserve`** — Account is preserved (not used for opportunistic traffic), with configurable floor percentages

The `AccountRoutingPolicy` enum and `routing_policy` column on the `Account` model were added.

### 3. Traffic Classes (`app/core/balancer/logic.py`, `app/db/models.py`)

Per-API-key traffic classification:
- **`foreground`** — Normal traffic (default)
- **`opportunistic`** — May only use explicitly expendable account capacity

The `traffic_class` column was added to the `ApiKey` model. The balancer's `select_account()` and `LoadBalancer.select_account()` now thread this through.

### 4. New `REAUTH_REQUIRED` Account Status

Previously, all permanent auth failures set accounts to `DEACTIVATED`. Now they're split:
- `REAUTH_REQUIRED` — For token expiry, session ended, invalid grant, etc. (recoverable via re-auth)
- `DEACTIVATED` — For account deleted, suspended, etc. (permanent)

New `REAUTH_REQUIRED_FAILURE_CODES` frozenset and `account_status_for_permanent_failure()` function route failures correctly.

### 5. Quota Planner Module (`app/modules/quota_planner/`)

A 7-file module that:
- **Forecasts demand** from historical request logs (binned into 15-min slots)
- **Computes routing costs** (`build_routing_costs()`) — per-account "cost" hints that nudge routing decisions (e.g., bonus for accounts with expiring quota windows, penalty for cold accounts)
- **Auto-warms accounts** — schedules lightweight API calls to proactively burn quota before reset
- Runs as a background scheduler (`QuotaPlannerScheduler`) with leader election

The routing cost system integrates into the load balancer: after hard eligibility and health tier filtering, accounts with lower planner cost are preferred.

### 6. New AccountState Fields

The `AccountState` dataclass was expanded with:
- `primary_reset_at`, `priority_used_percent`, `priority_secondary_used_percent`, `priority_reset_at`, `priority_capacity_credits` — for priority quota window tracking
- `limit_scoped_usage`, `ignore_standard_quota` — for models gated by separate quota pools
- `routing_policy` — per-account routing policy

### 7. New Settings

Dashboard settings added: `prefer_earlier_reset_window`, `single_account_id`, split budget thresholds (`primary`/`secondary`), `warmup_model`, `weekly_pace_working_days`, `additional_quota_routing_policies`, `quota_planner_scheduler_enabled`, `quota_planner_tick_seconds`.

### 8. Database Migrations

12 new content migrations + 1 merge head migration. The `reauth_required` migration also backfills existing `DEACTIVATED` accounts whose deactivation reason matches auth failure patterns.

### 9. Opportunistic Burn Filtering

Complex logic that determines which accounts can be used for opportunistic traffic:
- Weekly pace floor calculations
- Short-window floor calculations
- Emergency floor checks
- Preserve policy enforcement

## Files Changed (17 modified + new)

| File | Change |
|---|---|
| `app/core/balancer/__init__.py` | New exports for routing policies, traffic classes, costs |
| `app/core/balancer/logic.py` | +585 lines — all new strategies, policies, traffic classes, cost integration |
| `app/core/config/settings.py` | New settings (warmup_model, quota_planner_*, stream_idle_timeout bump) |
| `app/core/usage/__init__.py` | Monthly window support, `should_use_weekly_primary()`, `capacity_for_plan()` monthly |
| `app/core/upstream_proxy/` (new) | Copied because settings API imports `resolve_proxy_endpoint` from it |
| `app/db/models.py` | REAUTH_REQUIRED, AccountRoutingPolicy, routing_policy/traffic_class columns, QuotaPlanner models |
| `app/dependencies.py` | QuotaPlannerContext + provider |
| `app/main.py` | Quota planner scheduler startup/shutdown, router registration |
| `app/modules/proxy/load_balancer.py` | +787 lines — expanded selection inputs, quota planner integration, traffic class |
| `app/modules/quota_planner/` (new) | 7-file module: logic, api, repository, scheduler, schemas, warmup |
| `app/modules/settings/*` | Expanded schemas/api/service/repository for routing + quota settings |
| `app/modules/usage/additional_quota_keys.py` | `get_additional_quota_routing_policy()` + routing policy normalization |
| `app/db/alembic/versions/` | 12 content migrations + 1 merge head |
| `tests/unit/test_load_balancer.py` | +2556 lines — full test coverage for all strategies |
| `tests/unit/test_select_with_stickiness.py` | Updated for new signatures |
| `tests/unit/test_quota_planner.py` (new) | Quota planner unit tests |
| `tests/integration/test_load_balancer_integration.py` | Integration tests |

## Feature-Branch-Only Additions Preserved

Two things from the feature branch were woven into the pr-875 code:
1. **`app_session_terminated`** — Added to both `PERMANENT_FAILURE_CODES` and `REAUTH_REQUIRED_FAILURE_CODES` in `logic.py`
2. **`invalidate_account_client()`** — Call preserved in `mark_permanent_failure()` in `load_balancer.py` (clears per-account HTTP client session on deactivation)

## What Was NOT Merged (Skipped from PR 875)

- Auth guardian (`app/core/auth/guardian.py`) — background auth health checking
- Upstream proxy routing (`app/core/upstream_proxy/resolver.py` was copied only because settings API imports it)
- Codex client (`app/core/clients/codex.py`)
- Workspace identity (workspace_id, workspace_label, seat_type columns)
- Request log user-agent/failure metadata columns
- Free account monthly window
- Reports module
- Frontend changes (routing-settings.tsx, quota-planner components)

## Known Issues

1. **1 pre-existing test failure**: `test_load_selection_inputs_uses_registry_additional_quota_routing_policy_by_default` — this test expects `routing_policy_override="burn_first"` from the quota registry for `codex-spark`, but the registry JSON doesn't have that field. This test also fails on pr-875 itself.

2. **Duplicate `additional_quota_routing_policies_json` column** in pr-875's `DashboardSettings` model — fixed (removed duplicate).

3. **Migration heads**: The feature branch already had 36 migration heads from parallel development branches. The merge migration consolidates all into one. The pre-existing stale heads (from missing parent migrations) are a pre-existing issue handled by the app's custom migration tooling.

## Review Focus Areas

Please review the following aspects:

1. **Correctness of the merge**: Did we correctly identify and merge all dependencies? Are there missing imports or broken call chains?
2. **Feature branch preservation**: Is `app_session_terminated` correctly added to both failure code sets? Is `invalidate_account_client()` correctly threaded into the deactivation path?
3. **Migration chain**: Are the 12 content migrations correctly chained? Is the `reauth_required` migration's `down_revision` correctly rewritten from the skipped `merge_upstream_proxy_and_quota_planner_heads` to `routing_policy_persistence`?
4. **Skipped features**: Are there any references to skipped features (auth guardian, workspace identity, reports) that would cause runtime errors?
5. **Test coverage**: Are the 221 passing tests sufficient to validate the merge? Is the 1 failure acceptable as pre-existing?
6. **Settings API**: The upstream proxy module was copied because the settings API imports `resolve_proxy_endpoint`. Is this the right call, or should we have stubbed it?
