from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import SessionLocal
from .errors import APIError, api_error_handler
from .routes import auth_router, gallery_router
from .seed import init_db_and_seed

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as db:
        init_db_and_seed(db)
    yield


app = FastAPI(title="Honeybook Gallery API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(APIError)
async def _api_error(request: Request, exc: APIError) -> JSONResponse:
    return await api_error_handler(request, exc)


@app.exception_handler(StarletteHTTPException)
async def _http_exc(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Framework-raised errors (an unknown route's 404, a wrong method's 405)
    # collapse to the documented not_found envelope — no `{"detail": ...}` ever
    # leaks. The API's own 401/404s go through APIError, not here.
    return JSONResponse(status_code=404, content={"error": "not_found"})


@app.exception_handler(RequestValidationError)
async def _validation_exc(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Body/shape validation failures must speak the project's error envelope,
    not FastAPI's default 422 `{"detail": [...]}`.

    `/verify` collapses any malformed body to 401 invalid_code (the spec forbids
    enumerating *why* a code failed); a malformed `/favourite` body maps to the
    closest documented outcome, 404 not_found.
    """
    path = request.url.path
    if path.endswith("/verify"):
        return JSONResponse(status_code=401, content={"error": "invalid_code"})
    return JSONResponse(status_code=404, content={"error": "not_found"})


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Ops-only liveness probe (not part of the client `/api` contract).

    Used by the Docker healthcheck so the frontend container can wait for a
    ready backend before it starts proxying.
    """
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(gallery_router)

# Ensure the directory exists before mounting: StaticFiles validates it at
# import time, which is before the lifespan seed runs on a fresh checkout.
SEED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(SEED_DIR)), name="static")
