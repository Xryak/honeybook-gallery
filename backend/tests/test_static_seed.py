"""Static file serving, the image-variant pipeline, and seed idempotency."""

from __future__ import annotations


def test_healthz_ok(app_client):
    r = app_client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_both_variants_are_served_as_jpeg(app_client):
    for variant in ("thumb", "full"):
        r = app_client.get(f"/static/photos/{variant}/p_001.jpg")
        assert r.status_code == 200, variant
        assert r.headers["content-type"] == "image/jpeg"
        assert len(r.content) > 500


def test_thumbnail_is_smaller_than_full(app_client):
    thumb = app_client.get("/static/photos/thumb/p_001.jpg").content
    full = app_client.get("/static/photos/full/p_001.jpg").content
    # The pipeline really downscaled + compressed: the thumb is materially lighter.
    assert len(thumb) < len(full)


def test_static_unknown_photo_404(app_client):
    r = app_client.get("/static/photos/full/does_not_exist.jpg")
    assert r.status_code == 404


def test_render_variants_produces_correct_sizes(tmp_path, monkeypatch):
    from PIL import Image

    from app import images
    from app.seed import _base_image

    monkeypatch.setattr(images, "PHOTOS_DIR", tmp_path)
    images.render_variants("p_001", _base_image("p_001", 1))

    with Image.open(images.storage_path("p_001", images.FULL)) as full:
        assert full.size == (800, 600)
        assert full.format == "JPEG"
    with Image.open(images.storage_path("p_001", images.THUMBNAIL)) as thumb:
        # thumbnail() fits within the 320x240 box, preserving aspect ratio.
        assert thumb.size == (320, 240)
        assert thumb.width <= 320 and thumb.height <= 240


def test_load_font_falls_back_when_no_ttf(monkeypatch):
    from app import seed

    monkeypatch.setattr(seed, "_FONT_CANDIDATES", ("/definitely/missing.ttf",))
    font = seed._load_font(40)
    assert font is not None  # falls back to PIL's bundled default


def test_ensure_photo_files_is_idempotent(tmp_path, monkeypatch):
    """Second call regenerates nothing — variant mtimes stay put."""
    from app import images

    monkeypatch.setattr(images, "PHOTOS_DIR", tmp_path)
    from app import seed

    seed.ensure_photo_files()
    made = sorted(tmp_path.glob("**/*.jpg"))
    assert len(made) == 40  # 20 photos x 2 variants
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
