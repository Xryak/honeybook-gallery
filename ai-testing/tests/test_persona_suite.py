"""Tests OF the persona framework itself (runs in-process, no server, no key)."""

from __future__ import annotations

from pathlib import Path

import pytest
from persona_suite import PERSONAS
from persona_suite.client import GalleryClient
from persona_suite.llm import live_available
from persona_suite.report import to_dict, write_html, write_json
from persona_suite.runner import run_suite
from persona_suite.world import _structural_violations


@pytest.fixture(scope="module")
def client() -> GalleryClient:
    c = GalleryClient.in_process()
    yield c
    c.close()


def test_deterministic_suite_all_personas_pass(client):
    suite = run_suite(client, policy="deterministic")
    assert suite.passed, [
        (r.persona.id, r.failed_expectations, r.structural_violations, r.error)
        for r in suite.results
        if not r.passed
    ]
    assert len(suite.results) == len(PERSONAS)


def test_every_persona_produces_steps_and_checks(client):
    suite = run_suite(client, policy="deterministic")
    for r in suite.results:
        assert r.steps, f"{r.persona.id} ran no steps"
        assert r.expectations, f"{r.persona.id} asserted nothing"


def test_otp_oracle_returns_latest_code(client):
    client.request_otp("g_001")
    code = client.current_code("g_001")
    assert len(code) == 6 and code.isdigit()
    # verifying with the oracle's code authenticates
    resp = client.verify("g_001", code)
    assert resp.status == 200
    assert "token" in resp.body


def test_structural_invariants_flag_a_bad_response():
    assert _structural_violations(500, {"error": "x"})  # 5xx
    assert _structural_violations(403, {"error": "not_found"})  # undocumented status
    assert _structural_violations(404, {"detail": "nope"})  # wrong envelope
    assert _structural_violations(401, {"error": "weird_code"})  # bad enum
    assert _structural_violations(200, {"ok": True}) == []  # clean


def test_reports_serialize(client, tmp_path: Path):
    suite = run_suite(client, policy="deterministic")
    d = to_dict(suite)
    assert d["passed"] is True
    assert len(d["personas"]) == len(PERSONAS)

    write_json(suite, tmp_path / "p.json")
    write_html(suite, tmp_path / "p.html")
    assert (tmp_path / "p.json").stat().st_size > 0
    html = (tmp_path / "p.html").read_text()
    assert "Synthetic Persona Test Report" in html
    assert "Anna, the happy bride" in html


def test_live_mode_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert live_available() is False
