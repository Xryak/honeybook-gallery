"""Time-based expiry, exercised by advancing a frozen clock.

The other suite expires codes/sessions by mutating `expires_at` in the DB.
These tests instead drive real wall-clock advancement through the actual
`now + 10 min` logic, so an off-by-one in the TTL or a tz mistake would show up.
"""

from __future__ import annotations

from freezegun import freeze_time


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_otp_valid_just_before_expiry(app_client, latest_code):
    with freeze_time("2026-06-10 12:00:00") as clock:
        app_client.post("/api/galleries/g_001/otp")
        code = latest_code("g_001")
        clock.move_to("2026-06-10 12:09:59")  # 1s inside the 10-min window
        r = app_client.post("/api/galleries/g_001/verify", json={"code": code})
        assert r.status_code == 200


def test_otp_expired_just_after_window(app_client, latest_code):
    with freeze_time("2026-06-10 12:00:00") as clock:
        app_client.post("/api/galleries/g_001/otp")
        code = latest_code("g_001")
        clock.move_to("2026-06-10 12:10:01")  # 1s past expiry
        r = app_client.post("/api/galleries/g_001/verify", json={"code": code})
        assert r.status_code == 401
        assert r.json() == {"error": "invalid_code"}


def test_session_valid_just_before_expiry(app_client, mint_token):
    with freeze_time("2026-06-10 12:00:00") as clock:
        token = mint_token(app_client, "g_001")
        clock.move_to("2026-06-10 12:09:59")
        r = app_client.get("/api/galleries/g_001", headers=_auth(token))
        assert r.status_code == 200


def test_session_expired_just_after_window(app_client, mint_token):
    with freeze_time("2026-06-10 12:00:00") as clock:
        token = mint_token(app_client, "g_001")
        clock.move_to("2026-06-10 12:10:01")
        r = app_client.get("/api/galleries/g_001", headers=_auth(token))
        assert r.status_code == 401
        assert r.json() == {"error": "expired_session"}


def test_favorite_blocked_once_session_expired(app_client, mint_token):
    with freeze_time("2026-06-10 12:00:00") as clock:
        token = mint_token(app_client, "g_001")
        clock.move_to("2026-06-10 12:11:00")
        r = app_client.post(
            "/api/galleries/g_001/favourite",
            json={"photo_id": "p_001"},
            headers=_auth(token),
        )
        assert r.status_code == 401
        assert r.json() == {"error": "expired_session"}
