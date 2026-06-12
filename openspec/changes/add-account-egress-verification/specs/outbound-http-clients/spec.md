## ADDED Requirements

### Requirement: Egress verification probes use the account-bound client

Account egress verification probes MUST use the same per-account outbound HTTP client acquisition path as account-bound runtime traffic. The probe MUST NOT create a standalone `aiohttp.ClientSession`, MUST NOT use the shared global client, and MUST NOT use the save-time one-shot proxy session builder.

#### Scenario: Proxied account egress probe uses ProxyConnector session
- **WHEN** an account has `proxy_host` configured
- **AND** an egress verification probe runs for that account
- **THEN** the probe's HTTP GET uses the cached account-bound session backed by `ProxyConnector` matching stored proxy settings

#### Scenario: Direct account egress probe uses dedicated session
- **WHEN** an account has no proxy configured
- **AND** an egress verification probe runs for that account
- **THEN** the probe's HTTP GET uses that account's dedicated direct egress session
