## Why

Accounts are being invalidated by upstream after one to two days. The
mitigation should reduce bursty background account traffic and make
Codex-shaped requests carry stable per-account installation identity without
changing account egress routing.

## What Changes

- Increase the default background usage interval from 60 seconds to 120 seconds.
- Stagger background usage refreshes so the scheduler attempts one
  non-deactivated account per equal slice of the 120 second window instead of
  polling every account in one pass.
- Store a stable UUID-form Codex installation id per account and inject it as
  `x-codex-installation-id` metadata on response-create requests, or as the
  `x-codex-installation-id` header on compact requests, replacing any inbound
  client installation id.
- Treat refresh-bound `app_session_terminated` as a permanent session-ended
  failure so the affected account is deactivated instead of retried.

## Impact

- Proxied accounts still egress through their configured SOCKS5 proxy.
- Direct accounts still egress directly.
- Account-bound TLS remains the existing Codex TLS profile.
- Usage polling is less clustered and less frequent per account.
- Accounts whose refresh token returns `app_session_terminated` stop receiving
  routed traffic until they are re-authenticated.
- Existing accounts receive a generated Codex installation id during migration;
  new accounts receive one on creation.
