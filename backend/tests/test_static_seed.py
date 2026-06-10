"""Static file serving, seed image generation, and seed idempotency."""

from __future__ import annotations


def test_healthz_ok(app_client):
    r = app_client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_static_photo_is_served_as_jpeg(app_client):
    r = app_client.get("/static/photos/p_001.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert len(r.content) > 1000  # a real image, not an error page


def test_static_unknown_photo_404(app_client):
    r = app_client.get("/static/photos/does_not_exist.jpg")
    assert r.status_code == 404


def test_generate_image_is_800x600_jpeg(tmp_path):
    from PIL import Image

    from app.seed import _generate_image

    path = tmp_path / "p_001.jpg"
    _generate_image(path, "p_001", 1)
    assert path.exists()
    with Image.open(path) as im:
        assert im.size == (800, 600)
        assert im.format == "JPEG"


def test_load_font_falls_back_when_no_ttf(monkeypatch):
    from app import seed

    monkeypatch.setattr(seed, "_FONT_CANDIDATES", ("/definitely/missing.ttf",))
    font = seed._load_font(40)
    assert font is not None  # falls back to PIL's bundled default


def test_ensure_photo_files_skips_existing(tmp_path, monkeypatch):
    """Second call regenerates nothing (idempotent) — mtimes stay put."""
    from app import seed

    monkeypatch.setattr(seed, "PHOTOS_DIR", tmp_path)
    seed.ensure_photo_files()
    made = sorted(tmp_path.glob("*.jpg"))
    assert len(made) == 20
    mtimes = {p: p.stat().st_mtime_ns for p in made}

    seed.ensure_photo_files()
    assert all(p.stat().st_mtime_ns == mtimes[p] for p in made)


def test_seed_db_is_idempotent(app_client):
    from app.db import SessionLocal
    from app.models import Gallery, Photo
    from app.seed import seed_db

    with SessionLocal() as db:
        seed_db(db)  # already seeded by lifespan; this must add nothing
        seed_db(db)
        assert db.query(Gallery).count() == 2
        assert db.query(Photo).count() == 20
