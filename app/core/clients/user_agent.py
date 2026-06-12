from __future__ import annotations

import os
import platform
import re

from app.core.config.settings import get_settings

CODEX_CLI_ORIGINATOR = "codex_cli_rs"
_INVALID_UA_CHARS_RE = re.compile(r"[^A-Za-z0-9._/\-]")


def codex_cli_user_agent(*, version: str | None = None) -> str:
    """Build a Codex CLI-compatible User-Agent for background OpenAI calls."""

    effective_version = version or get_settings().model_registry_client_version
    return (
        f"{CODEX_CLI_ORIGINATOR}/{_sanitize_token(effective_version)} "
        f"({_platform_os_name()} {_platform_os_version()}; {_platform_arch()}) "
        f"{_terminal_token()}"
    )


def codex_cli_default_headers(*, version: str | None = None) -> dict[str, str]:
    return {
        "originator": CODEX_CLI_ORIGINATOR,
        "User-Agent": codex_cli_user_agent(version=version),
    }


def _platform_os_name() -> str:
    value = platform.system() or "unknown"
    return _sanitize_token(value)


def _platform_os_version() -> str:
    value = platform.release() or platform.version() or "unknown"
    return _sanitize_token(value)


def _platform_arch() -> str:
    value = platform.machine() or "unknown"
    return _sanitize_token(value)


def _terminal_token() -> str:
    term_program = _env_non_empty("TERM_PROGRAM")
    term_program_version = _env_non_empty("TERM_PROGRAM_VERSION")
    if term_program:
        token = f"{term_program}/{term_program_version}" if term_program_version else term_program
        return _sanitize_token(token)

    term = _env_non_empty("TERM")
    if term:
        return _sanitize_token(term)

    return "unknown"


def _env_non_empty(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value


def _sanitize_token(value: str) -> str:
    sanitized = _INVALID_UA_CHARS_RE.sub("_", value.strip())
    return sanitized or "unknown"
