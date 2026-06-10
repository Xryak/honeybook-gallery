from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import errors
from ..auth import _ensure_naive_utc, _utcnow
from ..db import get_db
from ..models import Gallery, GallerySession, OtpCode
from ..schemas import ErrorResponse, OtpResponse, VerifyRequest, VerifyResponse

router = APIRouter(prefix="/api/galleries", tags=["auth"])

OTP_TTL_SECONDS = 600
SESSION_TTL_SECONDS = 600

# Declared so FastAPI's generated OpenAPI documents the error envelope on every
# operation (keeps the auto-schema in sync with openapi.yaml and lets the
# schemathesis contract fuzzer assert status-code + body conformance).
_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Gallery or photo does not exist."}
}
_INVALID_CODE: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Code wrong/expired/used/absent."}
}


def _gallery_or_404(db: Session, gallery_id: str) -> Gallery:
    gallery = db.get(Gallery, gallery_id)
    if gallery is None:
        raise errors.not_found()
    return gallery


@router.post("/{id}/otp", response_model=OtpResponse, responses={**_NOT_FOUND})
def create_otp(id: str, db: Session = Depends(get_db)) -> OtpResponse:
    _gallery_or_404(db, id)

    # Invalidate any prior unused codes for this gallery.
    now = _utcnow().replace(tzinfo=None)
    prior_unused = (
        db.execute(
            select(OtpCode).where(
                OtpCode.gallery_id == id, OtpCode.used_at.is_(None)
            )
        )
        .scalars()
        .all()
    )
    for prior in prior_unused:
        prior.used_at = now

    code = f"{secrets.randbelow(10**6):06d}"
    expires_at = now + timedelta(seconds=OTP_TTL_SECONDS)
    db.add(OtpCode(gallery_id=id, code=code, expires_at=expires_at))
    db.commit()

    # Plain print so the user reading the backend terminal sees a clean line
    # regardless of uvicorn's log formatter. This is the channel the CLI relies
    # on — the API response deliberately never returns the code.
    print(f"[OTP] Gallery {id}: {code} (expires in 10 min)", flush=True)

    return OtpResponse(expires_in=OTP_TTL_SECONDS)


@router.post(
    "/{id}/verify",
    response_model=VerifyResponse,
    responses={**_INVALID_CODE, **_NOT_FOUND},
)
def verify_otp(
    id: str, body: VerifyRequest, db: Session = Depends(get_db)
) -> VerifyResponse:
    _gallery_or_404(db, id)

    # The 6-digit shape is enforced by VerifyRequest's pattern; a malformed body
    # is turned into 401 invalid_code by the RequestValidationError handler
    # before we get here, so by now body.code is well-formed.

    # Most recently issued code for this gallery, regardless of state.
    latest = db.execute(
        select(OtpCode)
        .where(OtpCode.gallery_id == id)
        .order_by(OtpCode.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest is None:
        raise errors.invalid_code()
    if latest.used_at is not None:
        raise errors.invalid_code()
    if _ensure_naive_utc(latest.expires_at) <= _utcnow():
        raise errors.invalid_code()
    if not secrets.compare_digest(latest.code, body.code):
        raise errors.invalid_code()

    now_naive = _utcnow().replace(tzinfo=None)
    latest.used_at = now_naive

    token = secrets.token_urlsafe(32)
    session = GallerySession(
        token=token,
        gallery_id=id,
        expires_at=now_naive + timedelta(seconds=SESSION_TTL_SECONDS),
    )
    db.add(session)
    db.commit()

    return VerifyResponse(token=token, expires_in=SESSION_TTL_SECONDS)
