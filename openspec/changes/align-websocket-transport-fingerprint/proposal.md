## Why

Account-bound Codex WebSocket handshakes should avoid Python-specific transport
signals when codex-lb is proxying a Codex CLI session. The current
`websockets` default offers `permessage-deflate` and emits library-managed
persona headers, which differs from the measured Rust/tungstenite Codex CLI
handshake shape.

## What Changes

- Disable WebSocket compression offers for upstream Codex Responses
  WebSocket handshakes.
- Send `Origin`, `user-agent`, `originator`, `chatgpt-account-id`,
  `openai-beta`, and `authorization` as an explicit custom header block.
- Keep per-account egress proxy and TLS behavior unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `outbound-http-clients`: Account-bound Codex Responses WebSocket handshakes
  must use the Codex CLI-compatible transport header shape.

## Impact

- Affected code: `app/core/clients/proxy_websocket.py`.
- Affected tests: `tests/unit/test_proxy_websocket_client.py`.
- No database, API schema, or operator configuration changes.
