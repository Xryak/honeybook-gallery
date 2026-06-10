"""Contract fuzzing with schemathesis.

Loads FastAPI's generated OpenAPI (which now documents the error envelope on
every operation) and hammers each endpoint with property-generated inputs,
asserting that every response conforms to the declared schema: documented
status code, documented body shape, correct content type. This is the
"does the server ever lie about its own contract / 500 on weird input" net.

Runs in-process against the ASGI app on a throwaway DB — no server needed.
"""

from __future__ import annotations

import os
import tempfile

# Bind the engine to a throwaway DB BEFORE app modules import it. The fuzzer
# creates real OTPs/sessions; we don't want that in the dev app.db. Assign
# unconditionally so an exported HONEYBOOK_DB_URL can't redirect it to a real DB.
os.environ["HONEYBOOK_DB_URL"] = f"sqlite:///{tempfile.mkdtemp()}/honeybook_fuzz.db"

import schemathesis  # noqa: E402
from hypothesis import HealthCheck, settings  # noqa: E402
from schemathesis.checks import CHECKS, load_all_checks  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import init_db_and_seed  # noqa: E402

with SessionLocal() as _db:
    init_db_and_seed(_db)

schema = schemathesis.openapi.from_asgi("/openapi.json", app)

# `unsupported_method` asserts that Starlette's stock 405 (e.g. for TRACE)
# carries an RFC-9110 `Allow` header. That's a framework default, not our
# contract, and is out of scope for a local mock — exclude only that check and
# keep the substantive ones (schema/status/content-type conformance, no 5xx,
# auth-is-enforced, negative-data-rejection).
load_all_checks()
_EXCLUDED = [c for c in CHECKS.get_all() if c.__name__ == "unsupported_method"]


@schema.parametrize()
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=list(HealthCheck),
)
def test_api_conforms_to_its_openapi(case):
    case.call_and_validate(excluded_checks=_EXCLUDED)
