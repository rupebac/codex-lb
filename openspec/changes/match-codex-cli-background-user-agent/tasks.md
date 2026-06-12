## 1. Identity Header Generation

- [x] 1.1 Add a centralized helper that builds Codex CLI-compatible background identity headers.
- [x] 1.2 Add unit coverage for the generated format and sanitization.

## 2. Outbound Client Integration

- [x] 2.1 Apply the generated identity headers as defaults for global managed HTTP sessions.
- [x] 2.2 Apply the generated identity headers as defaults for per-account direct and SOCKS managed HTTP sessions.
- [x] 2.3 Apply the generated identity headers as defaults for standalone aiohttp sessions.
- [x] 2.4 Preserve explicit and inbound identity headers over the session defaults.

## 3. Validation

- [x] 3.1 Run focused outbound HTTP client tests.
- [x] 3.2 Run OpenSpec validation.
