"""The world a persona acts in: executes actions, records a transcript, and
enforces contract invariants on every single response.

Invariants checked structurally on each step (regardless of persona):

* ``no_5xx``           — the server never returns a 5xx.
* ``documented_status``— status is one the contract documents (200/401/404).
* ``error_envelope``   — every 401/404 body is exactly ``{"error": <code>}`` with
  a code from the documented enum.

Persona-specific expectations are recorded via :meth:`World.expect`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .client import ApiResponse, GalleryClient
from .personas import Persona

ERROR_CODES = {"invalid_code", "expired_session", "not_found"}
DOCUMENTED_STATUSES = {200, 401, 404}


@dataclass
class Step:
    intent: str
    call: str
    status: int
    body: object
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


@dataclass
class Expectation:
    description: str
    passed: bool


def _structural_violations(status: int, body: object) -> list[str]:
    out: list[str] = []
    if status >= 500:
        out.append(f"5xx response ({status}) — server error")
    if status not in DOCUMENTED_STATUSES:
        out.append(f"undocumented status {status}")
    if status in (401, 404):
        if not (isinstance(body, dict) and set(body.keys()) == {"error"}):
            out.append(f"error body is not a bare {{'error': ...}} envelope: {body!r}")
        elif body["error"] not in ERROR_CODES:
            out.append(f"error code {body['error']!r} not in documented enum")
    return out


class World:
    def __init__(self, client: GalleryClient, persona: Persona) -> None:
        self.client = client
        self.persona = persona
        self.gallery = persona.gallery
        self.token: str | None = None
        self.transcript: list[Step] = []
        self.expectations: list[Expectation] = []
        self.known_photos: list[str] = []

    # -- recording -----------------------------------------------------------

    def _record(self, intent: str, call: str, resp: ApiResponse) -> Step:
        step = Step(
            intent=intent,
            call=call,
            status=resp.status,
            body=resp.body,
            violations=_structural_violations(resp.status, resp.body),
        )
        self.transcript.append(step)
        return step

    def expect(self, condition: bool, description: str) -> None:
        self.expectations.append(Expectation(description, bool(condition)))

    # -- actions (return the Step so scripts can branch) ---------------------

    def request_otp(self, gallery: str | None = None, intent: str = "request a code") -> Step:
        g = gallery or self.gallery
        return self._record(intent, f"POST /api/galleries/{g}/otp", self.client.request_otp(g))

    def current_code(self, gallery: str | None = None) -> str:
        return self.client.current_code(gallery or self.gallery)

    def verify(self, code: str, gallery: str | None = None, intent: str = "submit code") -> Step:
        g = gallery or self.gallery
        resp = self.client.verify(g, code)
        if resp.status == 200 and isinstance(resp.body, dict):
            self.token = resp.body.get("token")
        return self._record(intent, f"POST /api/galleries/{g}/verify", resp)

    def get_gallery(
        self,
        gallery: str | None = None,
        token: str | None = "__current__",
        intent: str = "open gallery",
    ) -> Step:
        g = gallery or self.gallery
        tok = self.token if token == "__current__" else token
        resp = self.client.get_gallery(g, tok)
        if resp.status == 200 and isinstance(resp.body, dict):
            self.known_photos = [p["id"] for p in resp.body.get("photos", [])]
        return self._record(intent, f"GET /api/galleries/{g}", resp)

    def favourite(
        self,
        photo_id: str,
        gallery: str | None = None,
        token: str | None = "__current__",
        intent: str = "toggle favorite",
    ) -> Step:
        g = gallery or self.gallery
        tok = self.token if token == "__current__" else token
        resp = self.client.favourite(g, tok, photo_id)
        return self._record(intent, f"POST /api/galleries/{g}/favourite", resp)
