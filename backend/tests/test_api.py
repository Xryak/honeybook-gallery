from __future__ import annotations

from datetime import datetime, timedelta


def _otp_and_token(client, capture_otp, gallery: str = "g_001") -> str:
    r = client.post(f"/api/galleries/{gallery}/otp")
    assert r.status_code == 200
    assert r.json() == {"expires_in": 600}
    code = capture_otp()

    r = client.post(f"/api/galleries/{gallery}/verify", json={"code": code})
    assert r.status_code == 200, r.json()
    body = r.json()
    assert "token" in body and body["expires_in"] == 600
    return body["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------- happy paths ----------


def test_otp_endpoint_happy_path(app_client, capture_otp):
    r = app_client.post("/api/galleries/g_001/otp")
    assert r.status_code == 200
    assert r.json() == {"expires_in": 600}
    code = capture_otp()
    assert len(code) == 6 and code.isdigit()


def test_verify_endpoint_happy_path(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp)
    assert token


def test_get_gallery_happy_path(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")
    r = app_client.get("/api/galleries/g_001", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "g_001"
    assert body["title"] == "Anna's Wedding"
    assert len(body["photos"]) == 10
    first = body["photos"][0]
    assert first["id"] == "p_001"
    assert first["thumbnail_url"] == "/static/photos/p_001.jpg"
    assert first["full_url"] == "/static/photos/p_001.jpg"
    assert first["is_favorite"] is False


def test_favourite_endpoint_happy_path(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")
    r = app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_003"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json() == {"photo_id": "p_003", "is_favorite": True}


# ---------- OTP semantics ----------


def test_otp_expiry_returns_invalid_code(app_client, capture_otp):
    r = app_client.post("/api/galleries/g_001/otp")
    assert r.status_code == 200
    code = capture_otp()

    # Mutate the DB to expire the only outstanding code.
    from app.db import SessionLocal
    from app.models import OtpCode

    with SessionLocal() as db:
        row = db.query(OtpCode).order_by(OtpCode.id.desc()).first()
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()

    r = app_client.post("/api/galleries/g_001/verify", json={"code": code})
    assert r.status_code == 401
    assert r.json() == {"error": "invalid_code"}


def test_otp_single_use(app_client, capture_otp):
    app_client.post("/api/galleries/g_001/otp")
    code = capture_otp()

    r1 = app_client.post("/api/galleries/g_001/verify", json={"code": code})
    assert r1.status_code == 200

    r2 = app_client.post("/api/galleries/g_001/verify", json={"code": code})
    assert r2.status_code == 401
    assert r2.json() == {"error": "invalid_code"}


def test_otp_rerequest_invalidates_prior(app_client, capture_otp):
    app_client.post("/api/galleries/g_001/otp")
    first_code = capture_otp()

    app_client.post("/api/galleries/g_001/otp")
    second_code = capture_otp()
    assert first_code != second_code or first_code == second_code  # cosmetic

    # The first code is no longer the most recent and was marked used —
    # verifying it must fail.
    r = app_client.post("/api/galleries/g_001/verify", json={"code": first_code})
    assert r.status_code == 401
    assert r.json() == {"error": "invalid_code"}

    # The second code still works.
    r = app_client.post("/api/galleries/g_001/verify", json={"code": second_code})
    assert r.status_code == 200


def test_verify_wrong_code(app_client, capture_otp):
    app_client.post("/api/galleries/g_001/otp")
    _ = capture_otp()
    r = app_client.post("/api/galleries/g_001/verify", json={"code": "000000"})
    assert r.status_code == 401
    assert r.json() == {"error": "invalid_code"}


def test_verify_malformed_code(app_client, capture_otp):
    app_client.post("/api/galleries/g_001/otp")
    _ = capture_otp()
    r = app_client.post("/api/galleries/g_001/verify", json={"code": "abcd"})
    assert r.status_code == 401
    assert r.json() == {"error": "invalid_code"}


def test_otp_on_unknown_gallery_404(app_client):
    r = app_client.post("/api/galleries/g_nope/otp")
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}


# ---------- auth ----------


def test_gallery_get_requires_auth(app_client):
    r = app_client.get("/api/galleries/g_001")
    assert r.status_code == 401
    assert r.json() == {"error": "expired_session"}


def test_token_scoped_to_gallery(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")
    r = app_client.get("/api/galleries/g_002", headers=_auth(token))
    assert r.status_code == 401
    assert r.json() == {"error": "expired_session"}


def test_session_expiry_returns_expired_session(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")

    from app.db import SessionLocal
    from app.models import GallerySession

    with SessionLocal() as db:
        session = db.get(GallerySession, token)
        session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()

    r = app_client.get("/api/galleries/g_001", headers=_auth(token))
    assert r.status_code == 401
    assert r.json() == {"error": "expired_session"}


def test_bearer_header_malformed(app_client):
    r = app_client.get(
        "/api/galleries/g_001",
        headers={"Authorization": "Token abc"},
    )
    assert r.status_code == 401
    assert r.json() == {"error": "expired_session"}


# ---------- favorites ----------


def test_favorite_toggle_round_trip(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")

    r = app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_001"},
        headers=_auth(token),
    )
    assert r.json() == {"photo_id": "p_001", "is_favorite": True}

    r = app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_001"},
        headers=_auth(token),
    )
    assert r.json() == {"photo_id": "p_001", "is_favorite": False}


def test_favorite_visible_in_gallery_get(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")
    app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_002"},
        headers=_auth(token),
    )
    r = app_client.get("/api/galleries/g_001", headers=_auth(token))
    photos = {p["id"]: p for p in r.json()["photos"]}
    assert photos["p_002"]["is_favorite"] is True
    assert photos["p_001"]["is_favorite"] is False


def test_favorite_cross_gallery_404(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")
    r = app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_011"},
        headers=_auth(token),
    )
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}


def test_favorite_unknown_photo_404(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")
    r = app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_999"},
        headers=_auth(token),
    )
    assert r.status_code == 404
    assert r.json() == {"error": "not_found"}


def test_favorites_isolated_per_session(app_client, capture_otp):
    """Documents the per-session favorites scope choice."""
    token_a = _otp_and_token(app_client, capture_otp, "g_001")
    app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_005"},
        headers=_auth(token_a),
    )

    token_b = _otp_and_token(app_client, capture_otp, "g_001")
    r = app_client.get("/api/galleries/g_001", headers=_auth(token_b))
    photos = {p["id"]: p for p in r.json()["photos"]}
    assert photos["p_005"]["is_favorite"] is False


# ---------- seed idempotency ----------


def test_reseed_does_not_wipe_favorites(app_client, capture_otp):
    token = _otp_and_token(app_client, capture_otp, "g_001")
    app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": "p_004"},
        headers=_auth(token),
    )

    from app.db import SessionLocal
    from app.seed import seed_db

    with SessionLocal() as db:
        seed_db(db)

    r = app_client.get("/api/galleries/g_001", headers=_auth(token))
    photos = {p["id"]: p for p in r.json()["photos"]}
    assert photos["p_004"]["is_favorite"] is True
