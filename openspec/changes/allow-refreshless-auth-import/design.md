## Context

Account import already accepts `tokens.refreshToken: ""` and stores it as empty
encrypted token material. Import with proxy additionally runs a refresh-backed
proxy probe, so adding proxy settings turns import into live refresh-token
validation. That is too strict for operator-provided auth files that intentionally
carry an empty refresh token.

The account table stores encrypted token fields as non-null bytes. The dashboard
auth-status mapper already treats decrypted empty refresh-token material as
`missing`, so a schema migration is not required to represent refreshless
imports.

## Goals / Non-Goals

**Goals:**

- Keep imported refresh-token absence visible as a missing refresh-token state.
- Avoid any OAuth refresh-token call during `auth.json` import solely because
  proxy fields are provided.
- Preserve refresh-backed proxy probes for OAuth proxy completion and proxy
  updates when a usable refresh token exists.

**Non-Goals:**

- Change OAuth add-account/token exchange contracts. OAuth responses still need
  access, refresh, and ID tokens.
- Make refreshless accounts indefinitely usable after their access token stops
  working.
- Add a database migration for nullable token columns.

## Decisions

1. Represent missing imported refresh tokens as encrypted empty strings.

   This keeps the existing non-null token column contract and uses the existing
   mapper behavior that reports empty decrypted refresh material as `missing`.
   A nullable-column migration was considered, but it would broaden the storage
   model and require more compatibility handling without improving operator
   behavior.

2. Use a connectivity-only proxy probe for auth.json import proxy fields.

   Import proxy validation should prove that the proposed SOCKS5 connection can
   establish HTTPS egress through the configured proxy. It must not send the
   imported refresh token to OAuth. A refresh-backed probe is still required for
   OAuth proxy completion and explicit proxy updates when a refresh token is
   present, because those paths intentionally rotate and persist fresh OAuth
   tokens.

## Risks / Trade-offs

- Refreshless accounts may fail once their access token expires -> callers get
  normal auth failure behavior and operators can re-authenticate or re-import.
- Connectivity-only proxy probes do not prove the imported credentials are
  refreshable -> this is intentional for import parity, while OAuth and
  explicit proxy-update paths retain refresh-backed validation when possible.
