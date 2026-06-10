"""Persona catalogue.

Each persona is pure data: an identity, a goal, quirks, and a natural-language
``blurb`` that doubles as the prompt the LLM policy/judge sees. The behavior for
the deterministic policy lives in ``deterministic.py``, keyed by ``id``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    gallery: str
    blurb: str
    traits: tuple[str, ...] = field(default_factory=tuple)


PERSONAS: list[Persona] = [
    Persona(
        id="happy_bride",
        name="Anna, the happy bride",
        gallery="g_001",
        blurb=(
            "Anna got the link to her wedding gallery. She types the code in "
            "correctly on the first try and excitedly favorites several of her "
            "favorite shots, expecting them to stay marked."
        ),
        traits=("cooperative", "goal: view gallery and favorite photos"),
    ),
    Persona(
        id="fat_fingers",
        name="Bob, all thumbs",
        gallery="g_001",
        blurb=(
            "Bob mistypes the 6-digit code a couple of times before getting it "
            "right. He expects clear rejection of the wrong codes and no lockout "
            "(the mock doesn't rate-limit), then a normal gallery afterwards."
        ),
        traits=("error-prone", "retries", "goal: eventually authenticate"),
    ),
    Persona(
        id="procrastinator",
        name="Pat, the procrastinator",
        gallery="g_002",
        blurb=(
            "Pat requests a code, wanders off, and by the time they come back a "
            "newer code has been issued. Their old code should be dead; they "
            "expect to recover simply by using the current one."
        ),
        traits=("slow", "goal: recover from a stale code"),
    ),
    Persona(
        id="boundary_tester",
        name="Nick, the nosy one",
        gallery="g_001",
        blurb=(
            "Nick authenticates to g_001 then pokes at boundaries: he tries to "
            "read g_002 with his g_001 token and tries to favorite a photo that "
            "belongs to g_002. He must be denied every time, with no data leak."
        ),
        traits=("adversarial", "goal: cross gallery boundaries (should fail)"),
    ),
    Persona(
        id="indecisive",
        name="Iris, can't decide",
        gallery="g_001",
        blurb=(
            "Iris toggles the same photo on and off many times. The server's "
            "final answer should match how many times she clicked, and the "
            "gallery view must agree with the last toggle."
        ),
        traits=("fickle", "goal: stress the favorite toggle"),
    ),
    Persona(
        id="malformed_prober",
        name="Sam, the prober",
        gallery="g_001",
        blurb=(
            "Sam throws junk at the API: empty codes, too-short codes, letters, a "
            "made-up photo id, and a missing token. Nothing should ever 500; "
            "every rejection should be the documented error envelope."
        ),
        traits=("chaotic", "goal: break the input handling (should be impossible)"),
    ),
]


def by_id(persona_id: str) -> Persona:
    for p in PERSONAS:
        if p.id == persona_id:
            return p
    raise KeyError(persona_id)
