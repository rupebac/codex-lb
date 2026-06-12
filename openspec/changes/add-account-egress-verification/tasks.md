## 1. OpenSpec & Database

- [x] 1.1 Create change `add-account-egress-verification` with proposal, design, spec deltas, tasks
- [x] 1.2 Add Alembic migration for egress columns on `accounts`
- [x] 1.3 Add model fields in `app/db/models.py`

## 2. Backend Core

- [x] 2.1 Add egress settings to `app/core/config/settings.py` (exact names/defaults per spec: probe enabled/url/timeout, guardrail mode, allow flags)
- [x] 2.2 Implement `app/core/clients/account_egress_probe.py` using `lease_account_http_client`
- [x] 2.3 Add `update_egress_probe_result` to accounts repository

## 3. Backend API & Service

- [x] 3.1 Add egress schemas to `app/modules/accounts/schemas.py`
- [x] 3.2 Implement `probe_account_egress` (invalidate `get_account_selection_cache()` after persist) and `get_account_egress_report` in service
- [x] 3.3 Add API routes POST `/egress/probe` and GET `/egress`
- [x] 3.4 Include egress status in `AccountSummary` via mappers

## 4. Guardrails

- [x] 4.1 Filter unsafe accounts in `load_balancer._load_selection_inputs` when mode is `block`

## 5. Frontend

- [x] 5.1 Update schemas, API client, hooks
- [x] 5.2 Update `account-proxy-section.tsx` with egress status, warnings, probe button

## 6. Tests & Validation

- [x] 6.1 Repository, probe unit, API integration tests
- [x] 6.2 Load balancer block-mode tests
- [x] 6.3 Frontend schema/API/component tests
- [x] 6.4 Run pytest, ruff, frontend build, `openspec validate --specs`
