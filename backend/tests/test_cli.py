"""CLI tests for `python -m app.cli` (Typer CliRunner, httpx mocked).

Covers the success path, the documented failure exits, and the in-process
`reseed` command. No network and no running server required.
"""

from __future__ import annotations

import contextlib

import httpx
import pytest
from typer.testing import CliRunner

from app.cli import app as cli_app

runner = CliRunner()


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def _combined(result) -> str:
    """CliRunner stdout/stderr handling differs across Click versions."""
    out = result.stdout or ""
    with contextlib.suppress(ValueError, AttributeError):
        out += result.stderr or ""
    return out


def test_send_otp_success(monkeypatch):
    monkeypatch.setattr(
        "app.cli.httpx.post", lambda *a, **k: _FakeResponse(200, '{"expires_in":600}')
    )
    result = runner.invoke(cli_app, ["send-otp", "g_001"])
    assert result.exit_code == 0
    assert "OK" in _combined(result)


def test_send_otp_gallery_not_found_exits_1(monkeypatch):
    monkeypatch.setattr(
        "app.cli.httpx.post", lambda *a, **k: _FakeResponse(404, '{"error":"not_found"}')
    )
    result = runner.invoke(cli_app, ["send-otp", "g_nope"])
    assert result.exit_code == 1
    assert "not found" in _combined(result).lower()


def test_send_otp_connect_error_exits_1(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.cli.httpx.post", boom)
    result = runner.invoke(cli_app, ["send-otp", "g_001"])
    assert result.exit_code == 1
    assert "running" in _combined(result).lower()


def test_send_otp_unexpected_status_exits_1(monkeypatch):
    monkeypatch.setattr(
        "app.cli.httpx.post", lambda *a, **k: _FakeResponse(500, "kaboom")
    )
    result = runner.invoke(cli_app, ["send-otp", "g_001"])
    assert result.exit_code == 1
    assert "Unexpected status" in _combined(result)


def test_send_otp_http_error_exits_1(monkeypatch):
    def boom(*a, **k):
        raise httpx.ReadTimeout("too slow")

    monkeypatch.setattr("app.cli.httpx.post", boom)
    result = runner.invoke(cli_app, ["send-otp", "g_001"])
    assert result.exit_code == 1


def test_send_otp_respects_base_url(monkeypatch):
    captured: dict[str, str] = {}

    def fake_post(url, *a, **k):
        captured["url"] = url
        return _FakeResponse(200, "{}")

    monkeypatch.setattr("app.cli.httpx.post", fake_post)
    result = runner.invoke(
        cli_app, ["send-otp", "g_001", "--base-url", "http://example.test:9000"]
    )
    assert result.exit_code == 0
    assert captured["url"] == "http://example.test:9000/api/galleries/g_001/otp"


@pytest.mark.usefixtures("app_client")
def test_reseed_is_idempotent_and_zero_exit():
    # `app_client` provisions and seeds a throwaway DB; reseed against it must be
    # a clean no-op that exits 0 and never raises.
    first = runner.invoke(cli_app, ["reseed"])
    second = runner.invoke(cli_app, ["reseed"])
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "Seed complete" in _combined(first)
