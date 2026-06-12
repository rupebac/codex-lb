## Context

codex-lb currently relies on pooled and standalone `aiohttp.ClientSession`
instances for outbound service traffic. When a call site does not pass a
`User-Agent`, aiohttp supplies its own default header. That affects token
refresh, OAuth bootstrap helpers, model fetches, version checks, bridge probes,
and other service-originated HTTP calls.

Codex CLI 0.139.0 builds its user agent from the originator, package version,
OS type/version, architecture, and a terminal token. The default first-party
originator is `codex_cli_rs`.

## Goals / Non-Goals

**Goals:**

- Generate Codex CLI-compatible background identity headers without hardcoding
  a stale single-platform string.
- Ensure background service HTTP calls do not leak `aiohttp/...`.
- Preserve real inbound `User-Agent` forwarding for active Codex client
  requests.

**Non-Goals:**

- Reproduce every Codex CLI terminal detection edge case.
- Add database fields or per-account user-agent storage.
- Change browser OAuth authorize `originator` defaults.

## Decisions

- Add a small pure helper for Codex CLI-compatible identity header generation.
  Rationale: the formatting belongs in one place and can be tested without
  network calls. Alternative: configure a static string; rejected because it
  goes stale and mismatches OS/architecture.
- Use `originator: codex_cli_rs` and
  `User-Agent: codex_cli_rs/<codex-version> (<os> <os-version>; <arch>) <terminal>`.
  Rationale: this mirrors Codex CLI's default header bundle closely enough for
  server-side header behavior while remaining deterministic in Python.
- Set default headers on managed and standalone outbound sessions.
  Rationale: background calls automatically get the fallback, while call sites
  that pass an explicit `User-Agent` still override it through request headers.
- Keep inbound forwarding behavior unchanged.
  Rationale: active user traffic should reflect the real client that initiated
  the request.

## Risks / Trade-offs

- OS version formatting may differ slightly from Rust `os_info`.
  Mitigation: use a stable Python approximation and keep the helper isolated
  for future refinement.
- Background traffic will identify as Codex CLI even when a deployment mostly
  serves Desktop clients.
  Mitigation: this change intentionally follows the requested CLI persona and
  still preserves inbound Desktop user agents on proxied traffic.
