from __future__ import annotations

import socket
from unittest.mock import patch

import aiohttp
import pytest
from aiohttp import web

from app.core.clients.user_agent import codex_cli_default_headers, codex_cli_user_agent

pytestmark = pytest.mark.unit


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def test_codex_cli_user_agent_matches_codex_cli_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.delenv("TERM_PROGRAM_VERSION", raising=False)

    with (
        patch("app.core.clients.user_agent.platform.system", return_value="Linux"),
        patch("app.core.clients.user_agent.platform.release", return_value="6.8.0-59-generic"),
        patch("app.core.clients.user_agent.platform.machine", return_value="x86_64"),
    ):
        user_agent = codex_cli_user_agent(version="0.139.0")

    assert user_agent == "codex_cli_rs/0.139.0 (Linux 6.8.0-59-generic; x86_64) xterm-256color"
    assert "aiohttp" not in user_agent


def test_codex_cli_user_agent_uses_term_program_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    monkeypatch.setenv("TERM_PROGRAM_VERSION", "1.101.0")
    monkeypatch.setenv("TERM", "xterm-256color")

    with (
        patch("app.core.clients.user_agent.platform.system", return_value="Darwin"),
        patch("app.core.clients.user_agent.platform.release", return_value="24.5.0"),
        patch("app.core.clients.user_agent.platform.machine", return_value="arm64"),
    ):
        user_agent = codex_cli_user_agent(version="0.139.0")

    assert user_agent == "codex_cli_rs/0.139.0 (Darwin 24.5.0; arm64) vscode/1.101.0"


def test_codex_cli_user_agent_sanitizes_header_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM_PROGRAM", "bad terminal")
    monkeypatch.setenv("TERM_PROGRAM_VERSION", "1\n2")

    with (
        patch("app.core.clients.user_agent.platform.system", return_value="Linux\n"),
        patch("app.core.clients.user_agent.platform.release", return_value="6 8"),
        patch("app.core.clients.user_agent.platform.machine", return_value="x86 64"),
    ):
        user_agent = codex_cli_user_agent(version="0.139 beta")

    assert user_agent == "codex_cli_rs/0.139_beta (Linux 6_8; x86_64) bad_terminal/1_2"


def test_codex_cli_default_headers_returns_user_agent() -> None:
    headers = codex_cli_default_headers(version="0.139.0")

    assert set(headers) == {"originator", "User-Agent"}
    assert headers["originator"] == "codex_cli_rs"
    assert headers["User-Agent"].startswith("codex_cli_rs/0.139.0 ")


@pytest.mark.asyncio
async def test_request_headers_override_session_defaults() -> None:
    captured: dict[str, str] = {}

    async def handler(request: web.Request) -> web.Response:
        captured["user_agent"] = request.headers["User-Agent"]
        captured["originator"] = request.headers["originator"]
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()

    try:
        async with aiohttp.ClientSession(headers=codex_cli_default_headers(version="0.139.0")) as session:
            async with session.get(
                f"http://127.0.0.1:{port}/",
                headers={
                    "originator": "explicit-originator",
                    "User-Agent": "explicit-client/1.0",
                },
            ) as response:
                assert response.status == 200
                await response.text()
    finally:
        await runner.cleanup()

    assert captured["user_agent"] == "explicit-client/1.0"
    assert captured["originator"] == "explicit-originator"


@pytest.mark.asyncio
async def test_session_defaults_survive_unrelated_request_headers() -> None:
    captured: dict[str, str] = {}

    async def handler(request: web.Request) -> web.Response:
        captured["accept"] = request.headers["Accept"]
        captured["user_agent"] = request.headers["User-Agent"]
        captured["originator"] = request.headers["originator"]
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()

    try:
        async with aiohttp.ClientSession(headers=codex_cli_default_headers(version="0.139.0")) as session:
            async with session.get(
                f"http://127.0.0.1:{port}/",
                headers={"Accept": "application/json"},
            ) as response:
                assert response.status == 200
                await response.text()
    finally:
        await runner.cleanup()

    assert captured["accept"] == "application/json"
    assert captured["originator"] == "codex_cli_rs"
    assert captured["user_agent"].startswith("codex_cli_rs/0.139.0 ")
