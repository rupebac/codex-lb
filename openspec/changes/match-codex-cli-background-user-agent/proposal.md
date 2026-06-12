## Why

Account-bound background calls can currently reach OpenAI with aiohttp's
default `User-Agent`, for example `aiohttp/3.x`. That differs from real Codex
CLI traffic and creates an avoidable client fingerprint on token refresh,
model fetch, and similar non-user-initiated calls.

## What Changes

- Generate Codex CLI-compatible background identity headers in codex-lb instead
  of relying on aiohttp defaults.
- Apply the generated `User-Agent` and `originator` headers to managed and
  standalone aiohttp sessions when the call site does not already provide them.
- Preserve inbound Codex client `User-Agent` values for proxied user requests.
- Add tests covering the generated format and header precedence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `outbound-http-clients`: outbound aiohttp sessions now have a required Codex
  CLI-compatible default identity header policy.

## Impact

- Affects outbound HTTP client construction and background call headers.
- No database, API response, or dashboard schema changes.
- Operators still get real inbound client `User-Agent` forwarding for proxied
  user traffic.
