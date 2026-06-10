"""The persona's "hands": a thin client over the gallery API.

Works two ways:

* ``in_process()`` — talks to the FastAPI app directly via an ASGI transport
  (no server, no ports) and reads OTP codes from the bound DB session. This is
  the default for ``make personas`` and CI.
* ``over_http(base_url, db_path)`` — talks to a running backend over HTTP and
  reads OTP codes out of the backend's SQLite file.

The OTP "oracle" stands in for a human reading the code off the backend
terminal — the API never returns the code over the wire, by design.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ApiResponse:
    status: int
    body: Any


def _bearer(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


class GalleryClient:
    def __init__(self, http: httpx.Client, otp_oracle: Callable[[str], str]) -> None:
        self._http = http
        self._otp_oracle = otp_oracle

    # -- constructors --------------------------------------------------------

    @classmethod
    def in_process(cls) -> GalleryClient:
        # Hermetic by contract: always bind to a throwaway DB, regardless of any
        # exported HONEYBOOK_DB_URL. The engine binds when app.db is first
        # imported below, so this must run first.
        os.environ["HONEYBOOK_DB_URL"] = f"sqlite:///{tempfile.mkdtemp()}/personas.db"
        from app.db import SessionLocal
        from app.main import app
        from app.models import OtpCode
        from app.seed import init_db_and_seed
        from fastapi.testclient import TestClient

        with SessionLocal() as db:
            init_db_and_seed(db)

        # Starlette's TestClient is a sync httpx.Client wired to the ASGI app —
        # no server, no ports, and it closes cleanly.
        http: httpx.Client = TestClient(app)

        def oracle(gallery: str) -> str:
            with SessionLocal() as db:
                row = (
                    db.query(OtpCode)
                    .filter(OtpCode.gallery_id == gallery)
                    .order_by(OtpCode.id.desc())
                    .first()
                )
                return row.code if row else ""

        return cls(http, oracle)

    @classmethod
    def over_http(cls, base_url: str, db_path: str) -> GalleryClient:
        http = httpx.Client(base_url=base_url.rstrip("/"), timeout=10.0)

        def oracle(gallery: str) -> str:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                cur = con.execute(
                    "SELECT code FROM otp_codes WHERE gallery_id = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (gallery,),
                )
                row = cur.fetchone()
                return row[0] if row else ""
            finally:
                con.close()

        return cls(http, oracle)

    # -- endpoint calls ------------------------------------------------------

    def _wrap(self, r: httpx.Response) -> ApiResponse:
        try:
            body = r.json()
        except ValueError:
            body = r.text
        return ApiResponse(status=r.status_code, body=body)

    def request_otp(self, gallery: str) -> ApiResponse:
        return self._wrap(self._http.post(f"/api/galleries/{gallery}/otp"))

    def verify(self, gallery: str, code: str) -> ApiResponse:
        return self._wrap(
            self._http.post(f"/api/galleries/{gallery}/verify", json={"code": code})
        )

    def get_gallery(self, gallery: str, token: str | None) -> ApiResponse:
        return self._wrap(
            self._http.get(f"/api/galleries/{gallery}", headers=_bearer(token))
        )

    def favourite(self, gallery: str, token: str | None, photo_id: str) -> ApiResponse:
        return self._wrap(
            self._http.post(
                f"/api/galleries/{gallery}/favourite",
                json={"photo_id": photo_id},
                headers=_bearer(token),
            )
        )

    def current_code(self, gallery: str) -> str:
        """The code a diligent user would currently read off the terminal."""
        return self._otp_oracle(gallery)

    def close(self) -> None:
        self._http.close()
