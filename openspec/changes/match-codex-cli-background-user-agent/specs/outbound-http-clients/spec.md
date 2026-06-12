## ADDED Requirements

### Requirement: Outbound aiohttp sessions use Codex CLI-compatible identity headers

Managed and standalone outbound `aiohttp.ClientSession` instances MUST send a default
`User-Agent` matching the Codex CLI user-agent shape and a default
`originator` matching the Codex CLI originator when the call site does
not provide explicit values. The default `User-Agent` shape MUST be:
`codex_cli_rs/<version> (<os> <os-version>; <arch>) <terminal>`.
The default `originator` MUST be `codex_cli_rs`.

The default background `User-Agent` MUST NOT contain `aiohttp`. Explicit
call-site `User-Agent` / `originator` headers and inbound Codex client
`User-Agent` / `originator` headers forwarded by proxy paths MUST take
precedence over the background defaults.

#### Scenario: Token refresh gets Codex CLI-compatible defaults
- **WHEN** the service performs an OAuth token refresh for an account
- **AND** the token refresh call site does not provide `User-Agent` or
  `originator`
- **THEN** the upstream request includes a `User-Agent` whose value starts
  with `codex_cli_rs/`
- **AND** the upstream request includes `originator: codex_cli_rs`
- **AND** the value does not include `aiohttp`

#### Scenario: Explicit identity headers win over background defaults
- **WHEN** an outbound call site supplies explicit `User-Agent` and
  `originator` headers
- **THEN** the upstream request uses those explicit values
- **AND** the generated background defaults do not replace them

#### Scenario: Standalone service sessions get identity defaults
- **WHEN** the service creates a standalone aiohttp session for version checks,
  bridge forwarding, or bridge readiness probes
- **THEN** the session default headers include `originator: codex_cli_rs`
- **AND** the session default `User-Agent` starts with `codex_cli_rs/`
- **AND** the value does not include `aiohttp`

#### Scenario: Proxied Codex requests preserve inbound identity headers
- **WHEN** a Codex client sends a proxied request with `originator:
  codex_cli_rs`
- **AND** the request includes `User-Agent:
  codex_cli_rs/1.2.3 (Linux 1.0; x86_64) xterm-256color`
- **THEN** the upstream request preserves those inbound headers
- **AND** the background defaults do not replace them
