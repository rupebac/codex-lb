"""Unit tests for the codex TLS context."""

from __future__ import annotations

import ssl

import pytest

from app.core.clients.account_tls import (
    build_codex_ssl_context,
    cached_codex_ssl_context,
)

pytestmark = pytest.mark.unit


def test_codex_context_uses_openssl_default_cipher_list() -> None:
    """The codex profile MUST NOT call ``set_ciphers`` — the OpenSSL
    default cipher list IS what we want (it matches Codex CLI's
    reqwest/native-tls cipher list on the same OpenSSL version).

    Smoke-check: the cipher count must match what
    ``ssl.create_default_context()`` produces with no modification.
    """

    bare = ssl.create_default_context()
    codex = build_codex_ssl_context()
    assert len(codex.get_ciphers()) == len(bare.get_ciphers())
    # First and last cipher names should match the bare default order.
    bare_names = [c["name"] for c in bare.get_ciphers()]
    codex_names = [c["name"] for c in codex.get_ciphers()]
    assert codex_names == bare_names


def test_codex_context_does_not_force_alpn(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Codex TLS profile MUST NOT mutate ALPN.

    Codex CLI's Linux reqwest/default-tls shape was measured without an
    ALPN extension. Forcing ``["http/1.1"]`` changes both JA3 and JA4.
    """

    calls: list[list[str]] = []
    original = ssl.SSLContext.set_alpn_protocols

    def spy(self: ssl.SSLContext, protocols: list[str]) -> None:
        calls.append(protocols)
        original(self, protocols)

    monkeypatch.setattr(ssl.SSLContext, "set_alpn_protocols", spy)
    codex = build_codex_ssl_context()

    assert isinstance(codex, ssl.SSLContext)
    assert calls == []


def test_cached_codex_context_is_singleton() -> None:
    """``cached_codex_ssl_context`` returns the SAME object on every
    call (``lru_cache(maxsize=1)``). Every account-bound request
    therefore shares one SSLContext and one JA3."""

    a = cached_codex_ssl_context()
    b = cached_codex_ssl_context()
    assert a is b
