from __future__ import annotations

from pydantic import BaseModel, Field


class OtpResponse(BaseModel):
    expires_in: int


class VerifyRequest(BaseModel):
    # Pattern mirrors openapi.yaml so the generated /openapi.json carries it too.
    # A non-matching body is caught by the RequestValidationError handler, which
    # maps it to 401 invalid_code (no enumeration of why).
    code: str = Field(pattern=r"^[0-9]{6}$", examples=["482910"])


class VerifyResponse(BaseModel):
    token: str
    expires_in: int


class PhotoOut(BaseModel):
    id: str
    thumbnail_url: str
    full_url: str
    is_favorite: bool


class GalleryOut(BaseModel):
    id: str
    title: str
    photos: list[PhotoOut]


class FavoriteRequest(BaseModel):
    photo_id: str


class FavoriteResponse(BaseModel):
    photo_id: str
    is_favorite: bool


class ErrorResponse(BaseModel):
    error: str
