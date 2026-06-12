## 1. WebSocket Transport Shape

- [x] 1.1 Disable upstream WebSocket compression offers for Codex Responses
  handshakes.
- [x] 1.2 Move Codex persona and account headers into an explicit custom
  handshake header block.
- [x] 1.3 Preserve existing account proxy, TLS, timeout, frame-size, and error
  handling behavior.

## 2. Verification

- [x] 2.1 Update unit tests for the expected WebSocket connect options and
  outgoing header shape.
- [x] 2.2 Capture the actual `connect_responses_websocket()` raw local
  handshake and compare it with the Rust/tungstenite baseline.
- [x] 2.3 Run targeted pytest and ruff checks for the changed clients and tests.
