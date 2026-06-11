from __future__ import annotations

import colorsys

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from . import images
from .db import Base, engine
from .models import Gallery, Photo

GALLERIES: list[tuple[str, str, range]] = [
    ("g_001", "Anna's Wedding", range(1, 11)),
    ("g_002", "Marco's Portrait Session", range(11, 21)),
]


def _photo_id(n: int) -> str:
    return f"p_{n:03d}"


# Tried in order; first one that loads wins. Covers macOS (Arial) and the
# Debian-slim Docker image (DejaVu, installed via fonts-dejavu-core).
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _base_image(photo_id: str, n: int, total: int = 20) -> Image.Image:
    """The full-resolution source for a seed photo: a unique hue with the photo
    id stamped in the center. In a real app this would be the user's upload; the
    derivative pipeline (`images.render_variants`) takes it from here."""
    hue = (n - 1) / total
    r, g, b = colorsys.hsv_to_rgb(hue, 0.55, 0.85)
    bg = (int(r * 255), int(g * 255), int(b * 255))

    img = Image.new("RGB", (800, 600), bg)
    draw = ImageDraw.Draw(img)
    font = _load_font(120)

    bbox = draw.textbbox((0, 0), photo_id, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(
        ((800 - text_w) / 2 - bbox[0], (600 - text_h) / 2 - bbox[1]),
        photo_id,
        fill=(255, 255, 255),
        font=font,
    )
    return img


def ensure_photo_files() -> None:
    """Generate every photo's compressed variants if any are missing (idempotent)."""
    for _, _, photo_range in GALLERIES:
        for n in photo_range:
            pid = _photo_id(n)
            if all(images.storage_path(pid, v).exists() for v in images.VARIANTS):
                continue
            images.render_variants(pid, _base_image(pid, n))


def seed_db(db: Session) -> None:
    """Insert the two galleries and their photos if galleries table is empty.

    Idempotent: re-running adds nothing if data is already present and never
    touches the favorites table.
    """
    if db.query(Gallery).count() > 0:
        return

    for gid, title, photo_range in GALLERIES:
        db.add(Gallery(id=gid, title=title))
        for n in photo_range:
            db.add(
                Photo(
                    id=_photo_id(n),
                    gallery_id=gid,
                    # Store the canonical (full) variant URL. In a real pipeline
                    # this would be a storage key; the thumbnail URL is derived
                    # from the photo id via `images.public_url`.
                    url=images.public_url(_photo_id(n), images.FULL),
                )
            )
    db.commit()


def init_db_and_seed(db: Session) -> None:
    Base.metadata.create_all(engine)
    ensure_photo_files()
    seed_db(db)
