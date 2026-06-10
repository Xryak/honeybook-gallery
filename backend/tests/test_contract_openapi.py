"""Conformance against the AUTHORITATIVE contract (`openapi.yaml`).

schemathesis (test_contract_fuzz) checks the app against the schema FastAPI
generates from its own routes. This suite is the other direction: it validates
real responses against the hand-written `openapi.yaml` that the frontend's TS
types are generated from — so backend and frontend can't silently drift apart.

For every documented response we exercise: (1) the status code is documented in
the spec, and (2) the JSON body validates against the spec's schema, with all
local `$ref`s inlined first.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.yaml"


@pytest.fixture(scope="session")
def spec() -> dict:
    return yaml.safe_load(OPENAPI_PATH.read_text())


def _pointer(spec: dict, ref: str):
    node = spec
    for raw in ref.lstrip("#/").split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        node = node[key]
    return node


def _deref(spec: dict, node):
    """Recursively inline every local `#/...` $ref (schemas are acyclic here)."""
    if isinstance(node, dict):
        if "$ref" in node and node["$ref"].startswith("#/"):
            return _deref(spec, _pointer(spec, node["$ref"]))
        return {k: _deref(spec, v) for k, v in node.items()}
    if isinstance(node, list):
        return [_deref(spec, v) for v in node]
    return node


def _response_schema(spec: dict, path: str, method: str, status: int) -> dict:
    responses = spec["paths"][path][method]["responses"]
    assert str(status) in responses, (
        f"{method.upper()} {path} returned undocumented status {status}"
    )
    entry = _deref(spec, responses[str(status)])
    return _deref(spec, entry["content"]["application/json"]["schema"])


def _check(spec, path, method, status, body) -> None:
    Draft202012Validator(_response_schema(spec, path, method, status)).validate(body)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _latest_code(gallery: str = "g_001") -> str:
    from app.db import SessionLocal
    from app.models import OtpCode

    with SessionLocal() as db:
        row = (
            db.query(OtpCode)
            .filter(OtpCode.gallery_id == gallery)
            .order_by(OtpCode.id.desc())
            .first()
        )
        return row.code


def test_otp_200_matches_spec(app_client, spec):
    r = app_client.post("/api/galleries/g_001/otp")
    assert r.status_code == 200
    _check(spec, "/api/galleries/{id}/otp", "post", 200, r.json())


def test_otp_404_matches_error_schema(app_client, spec):
    r = app_client.post("/api/galleries/g_nope/otp")
    assert r.status_code == 404
    _check(spec, "/api/galleries/{id}/otp", "post", 404, r.json())


def test_verify_200_matches_spec(app_client, spec):
    app_client.post("/api/galleries/g_001/otp")
    r = app_client.post("/api/galleries/g_001/verify", json={"code": _latest_code()})
    assert r.status_code == 200
    _check(spec, "/api/galleries/{id}/verify", "post", 200, r.json())


def test_verify_401_matches_error_schema(app_client, spec):
    app_client.post("/api/galleries/g_001/otp")
    r = app_client.post("/api/galleries/g_001/verify", json={"code": "000000"})
    assert r.status_code == 401
    _check(spec, "/api/galleries/{id}/verify", "post", 401, r.json())


def test_gallery_200_matches_gallery_schema(app_client, mint_token, spec):
    token = mint_token(app_client, "g_001")
    r = app_client.get("/api/galleries/g_001", headers=_auth(token))
    assert r.status_code == 200
    _check(spec, "/api/galleries/{id}", "get", 200, r.json())


def test_gallery_401_matches_error_schema(app_client, spec):
    r = app_client.get("/api/galleries/g_001")
    assert r.status_code == 401
    _check(spec, "/api/galleries/{id}", "get", 401, r.json())


def test_favourite_200_matches_spec(app_client, mint_token, spec):
    token = mint_token(app_client, "g_001")
    r = app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_001"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    _check(spec, "/api/galleries/{id}/favourite", "post", 200, r.json())


def test_favourite_404_matches_error_schema(app_client, mint_token, spec):
    token = mint_token(app_client, "g_001")
    r = app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_999"},
        headers=_auth(token),
    )
    assert r.status_code == 404
    _check(spec, "/api/galleries/{id}/favourite", "post", 404, r.json())


# ---- malformed bodies must speak the envelope, never FastAPI's 422 {detail} ----


def test_verify_missing_code_is_enveloped_401(app_client, spec):
    app_client.post("/api/galleries/g_001/otp")
    r = app_client.post("/api/galleries/g_001/verify", json={})
    assert r.status_code == 401
    assert r.json() == {"error": "invalid_code"}
    _check(spec, "/api/galleries/{id}/verify", "post", 401, r.json())


def test_verify_nonstring_code_is_enveloped_401(app_client, spec):
    app_client.post("/api/galleries/g_001/otp")
    r = app_client.post("/api/galleries/g_001/verify", json={"code": 123})
    assert r.status_code == 401
    assert r.json() == {"error": "invalid_code"}


def test_favourite_missing_photo_id_is_enveloped_404(app_client, mint_token, spec):
    token = mint_token(app_client, "g_001")
    r = app_client.post("/api/galleries/g_001/favourite", json={}, headers=_auth(token))
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}
    _check(spec, "/api/galleries/{id}/favourite", "post", 404, r.json())


def test_unsupported_method_is_enveloped_not_detail(app_client):
    # A 405 (wrong method) must not leak a {"detail": ...} body.
    r = app_client.put("/api/galleries/g_001/otp")
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}
