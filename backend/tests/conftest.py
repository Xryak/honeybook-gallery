from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch):
    """Yield a TestClient backed by a throwaway SQLite file.

    Imports must happen INSIDE the fixture so HONEYBOOK_DB_URL is in effect
    when the db module is first imported (the engine binds at import time).
    """
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("HONEYBOOK_DB_URL", f"sqlite:///{db_file}")

    # Force-reimport the app modules so the engine picks up the new URL.
    import importlib
    import sys

    for mod in [
        "app.main",
        "app.routes",
        "app.routes.auth",
        "app.routes.gallery",
        "app.auth",
        "app.seed",
        "app.models",
        "app.db",
        "app.errors",
        "app.schemas",
    ]:
        sys.modules.pop(mod, None)

    from fastapi.testclient import TestClient  # noqa: WPS433

    main = importlib.import_module("app.main")
    with TestClient(main.app) as client:
        yield client


@pytest.fixture
def latest_code():
    """Read the newest OTP code straight from the DB.

    More robust than scraping stdout under Hypothesis/freezegun, where captured
    output interleaves across many generated examples.
    """

    def _read(gallery_id: str = "g_001") -> str:
        from app.db import SessionLocal
        from app.models import OtpCode

        with SessionLocal() as db:
            row = (
                db.query(OtpCode)
                .filter(OtpCode.gallery_id == gallery_id)
                .order_by(OtpCode.id.desc())
                .first()
            )
            assert row is not None, f"no OTP issued for {gallery_id}"
            return row.code

    return _read


@pytest.fixture
def mint_token(latest_code):
    """Issue an OTP and exchange it for a session token in one call."""

    def _mint(client, gallery_id: str = "g_001") -> str:
        r = client.post(f"/api/galleries/{gallery_id}/otp")
        assert r.status_code == 200, r.text
        code = latest_code(gallery_id)
        r = client.post(f"/api/galleries/{gallery_id}/verify", json={"code": code})
        assert r.status_code == 200, r.text
        return r.json()["token"]

    return _mint


@pytest.fixture
def capture_otp(capfd):
    """Return a callable that extracts the latest [OTP] code from captured stdout."""

    def _read_last_code() -> str:
        out, _ = capfd.readouterr()
        last = None
        for line in out.splitlines():
            if line.startswith("[OTP]"):
                # Format: "[OTP] Gallery g_001: 482910 (expires in 10 min)"
                colon = line.find(":")
                paren = line.find("(", colon)
                if colon != -1 and paren != -1:
                    last = line[colon + 1 : paren].strip()
        assert last is not None, f"No [OTP] line in stdout. stdout was: {out!r}"
        return last

    return _read_last_code
