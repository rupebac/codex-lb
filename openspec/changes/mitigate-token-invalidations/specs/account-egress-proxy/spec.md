## ADDED Requirements

### Requirement: Account Codex installation identity is stable

Each account MUST have a stored Codex installation id in UUID string format.
New accounts MUST receive the id automatically when they are created, and
existing accounts MUST receive generated ids during database migration.

Account-bound Codex `/responses` and WebSocket `response.create` upstream
requests MUST send the stored per-account id as
`client_metadata["x-codex-installation-id"]`. Compact requests MUST send the
stored id as the `x-codex-installation-id` header and MUST NOT send
`client_metadata` in the compact request body. The service MUST replace any
inbound client-provided Codex installation id with the stored account id before
forwarding upstream.

#### Scenario: Existing accounts are backfilled
- **WHEN** the database migration runs on accounts that predate this field
- **THEN** every existing account row receives a non-empty UUID-form
  `codex_installation_id`

#### Scenario: Responses metadata uses the account id
- **WHEN** an account-bound Codex response request is forwarded upstream
- **THEN** the upstream payload includes
  `client_metadata["x-codex-installation-id"]` equal to the selected account's
  stored `codex_installation_id`
- **AND** any inbound client value for that metadata key is replaced

#### Scenario: Compact requests include the account id header
- **WHEN** an account-bound compact request is forwarded upstream
- **THEN** the upstream headers include `x-codex-installation-id` equal to the
  selected account's stored `codex_installation_id`
- **AND** the upstream compact request body does not include `client_metadata`
