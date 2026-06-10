from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, Header, Path
from sqlalchemy.orm import Session

from . import errors
from .db import get_db
from .models import GallerySession


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _ensure_naive_utc(dt: datetime) -> datetime:
    """SQLite drops tz; treat naive datetimes as UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def require_session(
    id: str = Path(...),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> GallerySession:
    """Validate a bearer token for the gallery in the path.

    Returns 401 expired_session if missing / malformed / expired / scoped to a
    different gallery. The path's `id` must match the session's `gallery_id`.
    """
    if not authorization:
        raise errors.expired_session()

    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise errors.expired_session()
    token = parts[1].strip()

    session = db.get(GallerySession, token)
    if session is None:
        raise errors.expired_session()
    if session.gallery_id != id:
        raise errors.expired_session()
    if _ensure_naive_utc(session.expires_at) <= _utcnow():
        raise errors.expired_session()

    return session
