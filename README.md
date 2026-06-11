# Honeybook Gallery

[![CI](https://github.com/Xryak/honeybook-gallery/actions/workflows/ci.yml/badge.svg)](https://github.com/Xryak/honeybook-gallery/actions/workflows/ci.yml)

A client-facing photo-gallery flow: open a link, enter a one-time code, browse a
grid of photos, and favorite the ones you love. OTP-gated, per-gallery scoped,
runs entirely locally. FastAPI + SQLite on the back, Vue 3 + Vite on the front.

> Built to the spec in [`task.md`](./task.md) and the plan in [`PLAN.md`](./PLAN.md),
> against the contract in [`openapi.yaml`](./openapi.yaml).

---

## Quick start — Docker (one command)

```bash
docker compose up --build
```

Then:

1. Open <http://localhost:8080/galleries/g_001> → you'll see the **code entry** screen.
2. Send yourself a code (it's "emailed" by being printed to the backend log):
   ```bash
   make docker-otp GALLERY=g_001     # or: docker compose exec backend python -m app.cli send-otp g_001
   docker compose logs backend | grep OTP
   #   [OTP] Gallery g_001: 482910 (expires in 10 min)
   ```
3. Type the 6 digits → the **gallery** appears with 10 thumbnails.
4. Click a photo to favorite it (filled heart + highlight); click again to unfavorite.
5. Favorites **survive a restart** (`docker compose restart backend`) — the DB is on a volume.

`g_002` ("Marco's Portrait Session") is a second gallery; a code for one gallery
does **not** unlock the other.

## Quick start — local (no Docker)

```bash
make install        # backend venv + frontend deps + Playwright chromium
make dev-backend    # terminal 1 → http://localhost:8000
make dev-frontend   # terminal 2 → http://localhost:5173
make otp GALLERY=g_001   # terminal 3 → code prints in terminal 1
```

Open <http://localhost:5173/galleries/g_001>. `make help` lists every target.

---

## The flow

```
  link ──▶ /galleries/g_001 ──▶ [enter code] ──POST /verify──▶ bearer token (localStorage)
                                      ▲                                    │
                              401 ────┘                          GET /galleries/g_001
                          (expired/clear)                                 │
                                                              grid of 10 thumbnails
                                                                          │
                                                          click ──POST /favourite──▶ toggle
```

- The code is **logged, never returned over the wire** — a human (or the CLI)
  reads it from the backend terminal, modeling the upstream email system.
- Tokens and OTP codes are **scoped per gallery** and expire after 10 minutes.
- 401 from any call clears that gallery's token and bounces back to code entry.

The full contract — every request/response shape, status code, and the
`{"error": "<code>"}` envelope — is in [`openapi.yaml`](./openapi.yaml), which is
also the source the frontend's TypeScript types are generated from.

---

## Testing — every layer

| Layer | What | Run |
|---|---|---|
| **Backend unit** | the four endpoints, OTP semantics, auth scoping, favorites | `make test-backend` |
| **Contract (authoritative)** | real responses validated against `openapi.yaml` (jsonschema) | `make test-backend` |
| **Contract fuzz** | [schemathesis](https://schemathesis.readthedocs.io) hammers every operation, asserting schema/status/envelope conformance | `make test-backend` |
| **Property-based** | [Hypothesis](https://hypothesis.readthedocs.io): code discrimination, toggle parity, "arbitrary input never 5xxs" | `make test-backend` |
| **Time-travel** | real 10-minute expiry via [freezegun](https://github.com/spulec/freezegun) | `make test-backend` |
| **CLI** | success / 404 / connection-refused / reseed (Typer runner) | `make test-backend` |
| **Frontend unit + component** | session store, typed fetch wrapper, `OtpEntry`, `GalleryGrid`, auth gating (Vitest + Testing Library) | `make test-frontend` |
| **E2E** | the real browser flow against real servers (Playwright) | `make test-e2e` |
| **AI personas** | synthetic users + contract invariants (see below) | `make personas` |

```
65 backend tests · 99% coverage · ruff + mypy clean
38 frontend unit/component tests · 3 Playwright E2E journeys
6 synthetic personas (42 invariant checks) · 6 framework meta-tests
```

The whole matrix runs in CI on every push — see
[`.github/workflows/ci.yml`](./.github/workflows/ci.yml).

### AI sauce — synthetic-persona testing

Instead of only hand-written scenarios, the suite defines **personas** (Anna the
happy bride, Bob who fat-fingers the code, Nick who probes gallery boundaries, …)
and lets each drive the real API. Whatever they do, contract **invariants** must
hold — never a 5xx, every error is the documented envelope, a token never crosses
galleries, favorites stay consistent.

```bash
make personas        # deterministic, in-process, no API key — runs in CI
make test-personas   # pytest the framework itself
```

With `ANTHROPIC_API_KEY` set, `--live` upgrades it: **Claude role-plays each
persona** (choosing actions via tool-use, reading the code off the terminal like
a person) and a second **Claude call judges** each journey for contract
correctness and UX humaneness. Every run writes a shareable HTML report to
`ai-testing/reports/`. Details in [`ai-testing/README.md`](./ai-testing/README.md).

---

## Architecture notes

- **Favorites are per session** (per token). When a session expires, that
  session's favorites disappear on the next sign-in — a clean, bounded mock
  choice (documented on `models.Favorite`).
- **Same-origin everywhere.** In dev the Vite proxy forwards `/api` + `/static`
  to the backend; in Docker nginx does the same. The frontend only ever uses
  relative URLs, so there's no CORS and no environment-specific base URL.
- **One source of truth.** `openapi.yaml` drives both the frontend's generated
  types and the backend's contract tests, so the two halves can't silently drift.
- **Idempotent seeding.** Galleries and 20 Pillow-generated photos are created on
  first boot and never wipe favorites on restart.
- **Image variant pipeline.** Each photo is rendered into two compressed JPEG
  variants — a light `thumb` for the grid and a larger `full` for click-to-enlarge
  — under `seed/photos/<variant>/`. `backend/app/images.py` defines the variants,
  storage layout, and URL scheme as a drop-in-shaped stand-in for a real upload →
  derivative → object-storage/CDN pipeline (commented inline).
- **`/healthz`** is an ops-only liveness probe (not part of the `/api` contract)
  used by the Docker healthcheck so the frontend waits for a ready backend.

## Project layout

```
Honeybook/
├── docker-compose.yml      one command → running app (backend + nginx frontend)
├── Makefile                every dev entrypoint (make help)
├── openapi.yaml            API contract (source of truth)
├── backend/                FastAPI + SQLAlchemy + SQLite, Dockerfile, pytest suite
├── frontend/               Vue 3 + Vite, Dockerfile + nginx, Vitest + Playwright
├── ai-testing/             synthetic-persona test suite (deterministic + live)
└── .github/workflows/ci.yml
```

## Links

- [`task.md`](./task.md) — the original spec
- [`PLAN.md`](./PLAN.md) — the implementation plan (Sessions A/B/C)
- [`openapi.yaml`](./openapi.yaml) — the API contract
- [`backend/README.md`](./backend/README.md) · [`ai-testing/README.md`](./ai-testing/README.md)
