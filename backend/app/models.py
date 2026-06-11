from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Gallery(Base):
    __tablename__ = "galleries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)

    photos: Mapped[list[Photo]] = relationship(
        back_populates="gallery", cascade="all, delete-orphan", order_by="Photo.id"
    )


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    gallery_id: Mapped[str] = mapped_column(ForeignKey("galleries.id"), nullable=False)
    # Canonical (full-size) variant URL. In a real pipeline this would be a
    # content-addressed storage key; the thumbnail URL is derived from the photo
    # id via `images.public_url`, so only one URL needs persisting.
    url: Mapped[str] = mapped_column(String, nullable=False)

    gallery: Mapped[Gallery] = relationship(back_populates="photos")


class Favorite(Base):
    """Favorites are stored per session.

    When a session expires the favorites visually disappear on the next OTP.
    Defensible mock-grade choice per PLAN.md — picked over per-gallery because
    it's the simplest and keeps state cleanly bounded by token lifetime.
    """

    __tablename__ = "favorites"

    session_token: Mapped[str] = mapped_column(
        ForeignKey("sessions.token", ondelete="CASCADE"), primary_key=True
    )
    photo_id: Mapped[str] = mapped_column(
        ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True
    )


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    gallery_id: Mapped[str] = mapped_column(ForeignKey("galleries.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GallerySession(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    gallery_id: Mapped[str] = mapped_column(ForeignKey("galleries.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
