## ADDED Requirements

### Requirement: Account Codex WebSocket handshakes use CLI-compatible transport shape

Account-bound Codex Responses WebSocket upstream handshakes MUST avoid
Python-library-specific compression offers and MUST send the Codex persona and
account headers as an explicit custom header block. The custom header block
MUST include `Origin`, `user-agent`, `originator`, `chatgpt-account-id`,
`openai-beta`, and `authorization` when those values are available for the
request. The handshake MUST continue to use the account's selected egress proxy
and TLS context.

#### Scenario: Account WebSocket handshake omits compression extensions

- **WHEN** the service opens an account-bound Codex Responses WebSocket
  upstream connection
- **THEN** the client handshake MUST NOT offer `Sec-WebSocket-Extensions:
  permessage-deflate`

#### Scenario: Account WebSocket handshake carries Codex persona headers

- **WHEN** the service opens an account-bound Codex Responses WebSocket
  upstream connection with an inbound Codex persona
- **THEN** the upstream handshake custom headers include `Origin`,
  `user-agent`, `originator`, `chatgpt-account-id`, `openai-beta`, and
  `authorization`
- **AND** the WebSocket client library MUST NOT generate an additional
  User-Agent header for the handshake

#### Scenario: Account WebSocket handshake preserves account egress controls

- **WHEN** the selected account has a configured SOCKS5 proxy
- **THEN** the upstream WebSocket handshake MUST use that proxy
- **AND** the upstream WebSocket TLS context remains the Codex account TLS
  profile
