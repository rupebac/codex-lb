"""Codex TLS context for account-bound upstream traffic."""

from __future__ import annotations

import ssl
from functools import lru_cache


def build_codex_ssl_context() -> ssl.SSLContext:
    """Build the SSLContext for Codex-shaped account traffic.

    Codex CLI (the upstream Rust client we proxy for) uses
    ``reqwest`` + the platform-default TLS backend. On Linux that is
    OpenSSL, and Python's stdlib ``ssl`` module is also a thin wrapper
    over OpenSSL. With the same OpenSSL version, an unmodified
    ``ssl.create_default_context()`` ClientHello matches Codex CLI's
    measured JA3/JA4 shape.

    Implementation: just ``ssl.create_default_context()``. NO
    ``set_ciphers`` (the OpenSSL default cipher list IS what we want),
    NO explicit ALPN mutation, NO per-account variation. The singleton
    cache below shares this context across every account-bound upstream
    request.
    """

    return ssl.create_default_context()


@lru_cache(maxsize=1)
def cached_codex_ssl_context() -> ssl.SSLContext:
    """Singleton cache for account-bound upstream TLS.

    There is no per-account variation: every request shares the same
    JA3 by design (see :func:`build_codex_ssl_context`). The
    ``maxsize=1`` cache makes the singleton property explicit.
    """

    return build_codex_ssl_context()


__all__ = [
    "build_codex_ssl_context",
    "cached_codex_ssl_context",
]
