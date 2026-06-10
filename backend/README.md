# Backend (Session A)

FastAPI + SQLAlchemy + SQLite. Implements the four endpoints in
[`../openapi.yaml`](../openapi.yaml) and the OTP CLI.

## Run

```bash
# from this directory
python3.11 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"

.venv/bin/uvicorn app.main:app --reload --port 8000

# in another terminal:
.venv/bin/python -m app.cli send-otp g_001
# the code is logged on the uvicorn terminal:
#   [OTP] Gallery g_001: 482910 (expires in 10 min)

# tests:
.venv/bin/python -m pytest -q
```

## Deviation from `PLAN.md`

The plan's text uses `python -m backend.cli send-otp ...` in one place but
also says `uvicorn app.main:app ...`. With a flat package layout you can only
have one of those without contortions, so this backend keeps the FastAPI
package named `app` (matching the `uvicorn` command) and the CLI is
`python -m app.cli`. Session C should adjust the Makefile target to match.

## Favorites scope

Favorites are stored **per session** (see the docstring on `models.Favorite`).
When the session expires the favorites visually disappear on the next OTP.
Defensible mock-grade choice — keeps state cleanly bounded by token lifetime.

## Layout

```
backend/
├── pyproject.toml
├── app/
│   ├── main.py           FastAPI app + lifespan seed + /static mount
│   ├── db.py             engine + session
│   ├── models.py         SQLAlchemy models
│   ├── schemas.py        pydantic request/response models
│   ├── auth.py           bearer-token dependency
│   ├── errors.py         APIError + JSON envelope handler
│   ├── seed.py           idempotent gallery + Pillow JPEG seeding
│   ├── cli.py            `python -m app.cli send-otp <gallery_id>`
│   └── routes/
│       ├── auth.py       POST /otp, POST /verify
│       └── gallery.py    GET /galleries/{id}, POST /favourite
├── seed/photos/          generated JPEGs (gitignored)
├── tests/                pytest suite
└── app.db                SQLite (gitignored, created at startup)
```
