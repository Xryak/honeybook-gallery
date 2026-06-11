"""Image derivative pipeline.

For this mock we generate two compressed JPEG variants per photo — a small,
heavily-compressed ``thumb`` for the grid and a larger ``full`` for
click-to-enlarge — and serve them as static files under
``seed/photos/<variant>/<photo_id>.jpg``.

The *shape* here is deliberately the shape a real pipeline would have, so the
future implementation is close to a drop-in replacement:

    FUTURE (real pipeline, on user upload):
      1. validate the upload (MIME sniff, max dimensions/size, strip EXIF),
      2. generate derivatives — these same `thumb`/`full` variants, plus modern
         formats (WebP/AVIF) and several `srcset` widths for responsive images,
      3. store them content-addressed (e.g. `<sha256>/<variant>.webp`) in object
         storage (S3/GCS) rather than the local `seed/` dir,
      4. serve through a CDN or an on-the-fly resize service, and persist the
         storage *key* (not a filesystem path) on the photo row.

Everything below is the local, dependency-free stand-in for steps (2) and (3):
the variant definitions, the storage layout, and the public URL scheme — the
three things the rest of the app and the frontend actually depend on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

PHOTOS_DIR = Path(__file__).resolve().parent.parent / "seed" / "photos"
# Public base path (served by the StaticFiles mount in main.py). Server-relative
# on purpose — the Vite proxy / nginx resolve it to the backend.
STATIC_BASE = "/static/photos"


@dataclass(frozen=True)
class Variant:
    """One rendition of a photo. `name` is both the URL segment and the storage
    subdirectory, so adding a variant (e.g. a 1600px `hero`) is a one-line change
    here and nothing else needs to know the layout."""

    name: str
    max_size: tuple[int, int]  # bounding box; aspect ratio is preserved
    quality: int  # JPEG quality (lower = smaller file)


# Grid thumbnails are small and aggressively compressed; the full variant backs
# the click-to-enlarge view. FUTURE: add WebP/AVIF renditions + more srcset widths.
THUMBNAIL = Variant("thumb", (320, 240), quality=70)
FULL = Variant("full", (800, 600), quality=85)
VARIANTS: tuple[Variant, ...] = (THUMBNAIL, FULL)


def storage_path(photo_id: str, variant: Variant) -> Path:
    """Where the variant's bytes live on disk (object-storage key, in prod)."""
    return PHOTOS_DIR / variant.name / f"{photo_id}.jpg"


def public_url(photo_id: str, variant: Variant) -> str:
    """The server-relative URL the API hands the client for this variant."""
    return f"{STATIC_BASE}/{variant.name}/{photo_id}.jpg"


def render_variants(photo_id: str, base: Image.Image) -> None:
    """Write every missing variant of ``base`` to disk (idempotent).

    `Image.thumbnail` downscales in place, preserving aspect ratio, and never
    upscales — so the `full` variant of an already-800x600 base is a re-encode
    at its quality, and `thumb` is a true downscale.
    """
    for variant in VARIANTS:
        path = storage_path(photo_id, variant)
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        rendition = base.copy()
        rendition.thumbnail(variant.max_size)
        # optimize=True squeezes a bit more out of the JPEG encoder. FUTURE: also
        # emit `.webp`/`.avif` here and let the client pick via <picture>.
        rendition.save(path, format="JPEG", quality=variant.quality, optimize=True)
