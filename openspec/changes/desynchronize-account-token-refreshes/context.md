## Context

This change addresses severity item #3 from the account-protection review:
synchronized token refreshes.

The important distinction is that the service already has a deterministic
per-account refresh threshold, but that alone does not prevent bursts. Once a
set of accounts is eligible, the usage updater or another background path can
still call OAuth refresh for many accounts back-to-back. This is visible even
when quota traffic is low because token refreshes are background OpenAI calls.

Composer should focus on OAuth refresh start behavior, not transport identity.
User-Agent, originator, TLS/JA3/JA4, and WebSocket fingerprint alignment are
separate severity item #2 work and should remain intact.

## Concrete Example

Assume 20 accounts were imported on the same day and the server was quiet for
several hours. When traffic or usage refresh resumes, several accounts may have
stale access tokens. Today, each 401-driven usage repair can call
`ensure_fresh(force=True)` in sequence, producing a visible OAuth refresh burst.

After this change:

- account schedules are lazily spread and persisted,
- usage-refresh repairs are background refreshes,
- only one background OAuth refresh starts at a time by default,
- starts are spaced by at least five minutes by default,
- live requests can still refresh the selected account when required,
- failures back off instead of looping,
- quota-exceeded accounts do not refresh in the background unless configured.

## Non-Goals

- Do not change the Codex CLI-compatible User-Agent/originator behavior.
- Do not change per-account proxy selection or egress verification.
- Do not implement JA3/JA4 changes here.
- Do not add dashboard UI unless needed for an implementation dependency.
