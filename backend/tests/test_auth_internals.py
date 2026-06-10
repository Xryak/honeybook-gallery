"""Edge cases in the auth dependency's internals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone


def test_ensure_naive_utc_normalizes_aware_datetime():
    from app.auth import _ensure_naive_utc

    aware = datetime(2026, 6, 10, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    out = _ensure_naive_utc(aware)
    # 12:00 +03:00 == 09:00 UTC
    assert out.hour == 9
    assert out.tzinfo == UTC


def test_unknown_but_well_formed_bearer_token_is_401(app_client):
    r = app_client.get(
        "/api/galleries/g_001",
        headers={"Authorization": "Bearer totally-made-up-token"},
    )
    assert r.status_code == 401
    assert r.json() == {"error": "expired_session"}


def test_bearer_with_empty_token_is_401(app_client):
    r = app_client.get(
        "/api/galleries/g_001",
        headers={"Authorization": "Bearer    "},
    )
    assert r.status_code == 401
    assert r.json() == {"error": "expired_session"}
