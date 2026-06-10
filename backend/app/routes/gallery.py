from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import errors
from ..auth import require_session
from ..db import get_db
from ..models import Favorite, Gallery, GallerySession, Photo
from ..schemas import (
    ErrorResponse,
    FavoriteRequest,
    FavoriteResponse,
    GalleryOut,
    PhotoOut,
)

router = APIRouter(prefix="/api/galleries", tags=["gallery"])

_AUTH_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing/expired/wrong-gallery token."},
    404: {"model": ErrorResponse, "description": "Gallery or photo does not exist."},
}


@router.get("/{id}", response_model=GalleryOut, responses={**_AUTH_ERRORS})
def get_gallery(
    id: str,
    session: GallerySession = Depends(require_session),
    db: Session = Depends(get_db),
) -> GalleryOut:
    gallery = db.get(Gallery, id)
    if gallery is None:
        raise errors.not_found()

    favorite_ids = {
        photo_id
        for (photo_id,) in db.query(Favorite.photo_id)
        .filter(Favorite.session_token == session.token)
        .all()
    }

    return GalleryOut(
        id=gallery.id,
        title=gallery.title,
        photos=[
            PhotoOut(
                id=p.id,
                thumbnail_url=p.url,
                full_url=p.url,
                is_favorite=p.id in favorite_ids,
            )
            for p in gallery.photos
        ],
    )


@router.post("/{id}/favourite", response_model=FavoriteResponse, responses={**_AUTH_ERRORS})
def toggle_favorite(
    id: str,
    body: FavoriteRequest,
    session: GallerySession = Depends(require_session),
    db: Session = Depends(get_db),
) -> FavoriteResponse:
    photo = db.get(Photo, body.photo_id)
    if photo is None or photo.gallery_id != id:
        raise errors.not_found()

    existing = db.get(Favorite, (session.token, photo.id))
    if existing is None:
        db.add(Favorite(session_token=session.token, photo_id=photo.id))
        is_favorite = True
    else:
        db.delete(existing)
        is_favorite = False
    db.commit()

    return FavoriteResponse(photo_id=photo.id, is_favorite=is_favorite)
