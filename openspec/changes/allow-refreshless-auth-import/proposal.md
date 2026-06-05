## Why

Operators sometimes import `auth.json` payloads that contain usable access and ID
tokens with an empty refresh token. Import must remain a permissive credential
ingestion path; adding proxy settings to the same import must not silently turn
that path into mandatory refresh-token validation.

## What Changes

- Preserve the imported account's "missing refresh token" state so dashboard
  token status and runtime refresh behavior can report it accurately.
- Keep refresh-backed proxy probing when a refresh token is available.
- Permit import-with-proxy with an empty refresh token by persisting the proxy
  configuration without forcing an OAuth refresh-token call during import.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `account-egress-proxy`: import-with-proxy no longer requires a refresh token
  and must not force refresh-token validation for imports with empty refresh
  token material.

## Impact

- Backend account import parser and persistence.
- Per-account proxy persistence/probe flow.
- Integration/unit coverage for import-with-proxy and proxy updates with empty
  refresh token material.
