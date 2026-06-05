## MODIFIED Requirements

### Requirement: Save-time end-to-end proxy probe

The service MUST validate proposed proxy configurations before persisting them.
For OAuth proxy completion and explicit proxy updates on accounts with a stored
refresh token, validation MUST construct a one-shot `ProxyConnector` from the
proposed configuration and perform a real OAuth token refresh against the
upstream OAuth endpoint using the account's current refresh token. The probe
MUST classify the outcome into one of: `ok`, `proxy_connect`, `proxy_auth`,
`tls`, `upstream_status`, `invalid_response`, `timeout`. Only `ok` MUST persist
the configuration, and any rotated OAuth tokens returned by a successful refresh
MUST be persisted atomically with the proxy configuration.

For `auth.json` import with request-level proxy fields, validation MUST use a
connectivity-only HTTPS probe through the proposed proxy and MUST NOT perform an
OAuth refresh-token request. A received upstream HTTP response MUST count as
successful proxy connectivity for this import-time probe. Import-time proxy
validation MUST NOT require `tokens.refreshToken` to be non-empty.

For explicit proxy updates on accounts without a stored refresh token, the
service MUST use the same connectivity-only proxy probe and MUST NOT send an
empty refresh token upstream.

#### Scenario: Successful refresh-backed probe persists the proxy
- **WHEN** an operator submits a valid proxy configuration for an account with
  a stored refresh token outside the `auth.json` import flow
- **AND** the end-to-end OAuth refresh through the proxy returns 2xx
- **THEN** the proxy configuration is persisted on the account
- **AND** any rotated OAuth tokens are persisted atomically with the proxy
  configuration
- **AND** the API response includes the new `AccountProxySummary`

#### Scenario: Probe failure rejects the proxy with a typed reason
- **WHEN** an operator submits a proxy configuration that the selected probe
  classifies as `proxy_connect`, `proxy_auth`, `tls`, `upstream_status`,
  `invalid_response`, or `timeout`
- **THEN** the proxy configuration is NOT persisted
- **AND** the API responds 422 with `error.code=proxy_probe_failed` and
  `error.reason` equal to the probe classification

#### Scenario: Import with proxy does not validate refresh token
- **WHEN** an operator imports an `auth.json` file and submits proxy settings
  in the same request payload
- **THEN** the service validates proxy connectivity before inserting or updating
  the account row
- **AND** the service does NOT perform an OAuth refresh-token request for the
  import-time proxy validation
- **AND** the account is persisted with the exact imported token material and
  proxy fields atomically before any import-time usage refresh runs
- **AND** the account's cached egress client MUST be invalidated before any
  import-time usage refresh runs

#### Scenario: Import with proxy accepts empty refresh token
- **WHEN** an operator imports an `auth.json` payload with `tokens.refreshToken`
  set to an empty string
- **AND** submits proxy settings in the same request payload
- **AND** the connectivity-only proxy probe succeeds
- **THEN** `POST /api/accounts/import` succeeds
- **AND** the account is persisted with the proxy configuration
- **AND** the account's token status reports the refresh token as missing

### Requirement: Auth.json payload does not carry proxy configuration

The `auth.json` payload MUST be limited to OpenCode-compatible account
credentials and MUST NOT carry proxy fields or proxy credentials. Import
proxy behavior is a separate request-level concern.

The import endpoint MAY accept proxy fields as request-level form fields in
the same multipart call as `POST /api/accounts/import`; those are applied via
the account egress persistence path, while the `auth.json` JSON content itself
is ignored for proxy state.

#### Scenario: Import without proxy form does not modify proxy state
- **WHEN** an operator imports an `auth.json` for an account
- **AND** the multipart request carries no proxy form fields
- **THEN** any existing proxy configuration on that account is preserved
  unchanged
- **AND** no proxy fields are read from the `auth.json` payload

#### Scenario: Import with proxy form applies proxy atomically with account insert
- **WHEN** an operator imports an `auth.json` and submits explicit proxy form
  fields in the request
- **THEN** the service validates the provided proxy before persisting the account
- **AND** persists the account and proxy atomically on validation success
- **AND** the proxy state update does not come from the `auth.json` payload

#### Scenario: Export of an account does not include proxy state
- **WHEN** an operator exports an account
- **THEN** the exported `auth.json` does NOT include any proxy fields
