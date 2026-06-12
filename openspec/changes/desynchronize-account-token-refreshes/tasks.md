## 1. OpenSpec & Schema

- [x] 1.1 Validate this change with `openspec validate desynchronize-account-token-refreshes --strict`
- [x] 1.2 Add Alembic migration for token refresh schedule columns on `accounts`
- [x] 1.3 Add model fields in `app/db/models.py`
- [x] 1.4 Extend account repository ports and implementations to update refresh schedule metadata atomically with token/status writes

## 2. Settings & Scheduler

- [x] 2.1 Add token refresh pacing/backoff settings to `app/core/config/settings.py`
- [x] 2.2 Add token refresh source/context types and decision helpers near the auth refresh/auth manager boundary
- [x] 2.3 Add a process-local background token-refresh pacer enforcing concurrency and minimum start spacing
- [x] 2.4 Add lazy initialization for null `token_refresh_next_allowed_at` using stable per-account spread

## 3. Auth Manager Integration

- [x] 3.1 Extend `AuthManager.ensure_fresh(...)` to accept refresh source/context while preserving existing callers
- [x] 3.2 Route live proxy requests through live-request refresh semantics
- [x] 3.3 Route usage refresh, auth guardian, warmup, startup, and manual fleet refresh through background semantics
- [x] 3.4 Persist refresh attempt/result/schedule metadata on success, transient failure, permanent failure, and scheduler skip
- [x] 3.5 Preserve `_REFRESH_SINGLEFLIGHT`, refresh-token-material change detection, deactivation behavior, and `proxy_token_refresh_limit` admission

## 4. Usage Refresh Integration

- [x] 4.1 Change usage-refresh 401 token repair to use background refresh semantics instead of live-request bypass
- [x] 4.2 Treat scheduler deferral as a non-successful usage refresh without deactivating or marking the account unhealthy
- [x] 4.3 Keep existing usage auth failure cooldown behavior for upstream 401/403 fetch failures

## 5. Tests

- [x] 5.1 Unit tests for schedule initialization, deterministic spread, due/not-due decisions, and hard-max behavior
- [x] 5.2 Unit tests for background pacer concurrency and minimum start spacing using fake time/sleep
- [x] 5.3 Unit tests proving live request refresh bypasses background pacing but still uses singleflight/admission
- [x] 5.4 Unit tests proving usage-refresh 401 repair is background-paced/deferred
- [x] 5.5 Unit tests for skip policy: deactivated, paused, reauth-required, and quota-exceeded accounts
- [x] 5.6 Unit tests for transient failure backoff and permanent failure deactivation metadata
- [x] 5.7 Migration tests for fresh database and historical account rows

## 6. Validation

- [x] 6.1 Run focused pytest for auth manager, usage updater, repository, migration, and scheduler tests
- [x] 6.2 Run `uv run ruff check app tests`
- [x] 6.3 Run `openspec validate desynchronize-account-token-refreshes --strict`
- [x] 6.4 Run `openspec validate --specs`
