from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse


class APIError(HTTPException):
    """HTTPException that serializes to the project's error envelope `{"error": "<code>"}`.

    Codes are constrained to the openapi.yaml enum: invalid_code, expired_session, not_found.
    """

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(status_code=status_code, detail=code)
        self.code = code


def invalid_code() -> APIError:
    return APIError(401, "invalid_code")


def expired_session() -> APIError:
    return APIError(401, "expired_session")


def not_found() -> APIError:
    return APIError(404, "not_found")


async def api_error_handler(_request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code})
