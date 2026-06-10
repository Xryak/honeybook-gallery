"""Deterministic (offline, reproducible) persona behaviors.

Each persona drives a scripted-but-realistic journey through the API and asserts
its own goal-level expectations via ``world.expect``. Structural contract
invariants are enforced automatically by :class:`World` on every step.

No randomness, no network egress, no API key — this is the policy that runs in
CI and backs ``make personas`` by default.
"""

from __future__ import annotations

from .world import World


def _a_wrong_code(real: str) -> str:
    """A 6-digit string guaranteed to differ from ``real``."""
    return "000000" if real != "000000" else "111111"


def run(world: World) -> None:
    dispatch = {
        "happy_bride": _happy_bride,
        "fat_fingers": _fat_fingers,
        "procrastinator": _procrastinator,
        "boundary_tester": _boundary_tester,
        "indecisive": _indecisive,
        "malformed_prober": _malformed_prober,
    }
    dispatch[world.persona.id](world)


def _authenticate(world: World) -> None:
    world.request_otp(intent="request the access code")
    world.verify(world.current_code(), intent="type the code from the terminal")


def _happy_bride(world: World) -> None:
    world.request_otp(intent="request the access code")
    step = world.verify(world.current_code(), intent="type the correct code")
    world.expect(step.status == 200, "correct code authenticates")

    step = world.get_gallery(intent="open the wedding gallery")
    world.expect(step.status == 200, "gallery loads")
    world.expect(
        isinstance(step.body, dict) and len(step.body.get("photos", [])) == 10,
        "gallery shows 10 photos",
    )

    for photo in ("p_001", "p_003", "p_005"):
        s = world.favourite(photo, intent=f"heart {photo}")
        world.expect(
            s.status == 200 and s.body.get("is_favorite") is True,
            f"{photo} becomes favorite",
        )

    final = world.get_gallery(intent="re-open to confirm favorites stuck")
    favs = {p["id"] for p in final.body.get("photos", []) if p["is_favorite"]}
    world.expect(favs == {"p_001", "p_003", "p_005"}, "all three favorites persist")


def _fat_fingers(world: World) -> None:
    world.request_otp(intent="request the access code")
    real = world.current_code()
    wrong = _a_wrong_code(real)

    for attempt in (1, 2):
        s = world.verify(wrong, intent=f"mistype the code (attempt {attempt})")
        world.expect(s.status == 401, f"wrong code attempt {attempt} is rejected")
        world.expect(
            isinstance(s.body, dict) and s.body.get("error") == "invalid_code",
            "rejection uses invalid_code (no enumeration of why)",
        )

    s = world.verify(real, intent="finally type it right")
    world.expect(s.status == 200, "correct code works despite earlier failures")
    g = world.get_gallery(intent="open the gallery — no lockout expected")
    world.expect(g.status == 200, "no lockout after wrong attempts")


def _procrastinator(world: World) -> None:
    world.request_otp(intent="request a code, then get distracted")
    stale = world.current_code()
    world.request_otp(intent="come back later; a fresh code is issued")

    s = world.verify(stale, intent="try the old code out of habit")
    world.expect(s.status == 401, "the rotated-away code no longer works")

    s = world.verify(world.current_code(), intent="use the current code")
    world.expect(s.status == 200, "recovers by using the current code")


def _boundary_tester(world: World) -> None:
    _authenticate(world)  # token scoped to g_001
    world.expect(world.token is not None, "authenticated to g_001")

    s = world.get_gallery(gallery="g_002", intent="read g_002 with a g_001 token")
    world.expect(s.status == 401, "token does not cross galleries (read)")
    world.expect(
        isinstance(s.body, dict) and s.body.get("error") == "expired_session",
        "cross-gallery read denied as expired_session",
    )

    s = world.favourite("p_011", gallery="g_001", intent="favorite a g_002 photo via g_001")
    world.expect(s.status == 404, "a photo from another gallery is not found here")

    s = world.favourite("p_001", gallery="g_002", intent="favorite in g_002 with g_001 token")
    world.expect(s.status == 401, "token does not cross galleries (write)")


def _indecisive(world: World) -> None:
    _authenticate(world)
    clicks = 5  # odd -> ends favorited
    last = None
    for i in range(1, clicks + 1):
        s = world.favourite("p_002", intent=f"toggle p_002 ({i})")
        world.expect(s.status == 200, f"toggle {i} succeeds")
        world.expect(
            s.body.get("is_favorite") is (i % 2 == 1),
            f"toggle {i} parity is correct",
        )
        last = s.body.get("is_favorite")

    world.expect(last is True, "after an odd number of clicks, it ends favorited")
    g = world.get_gallery(intent="confirm the view agrees with the last toggle")
    state = {p["id"]: p["is_favorite"] for p in g.body.get("photos", [])}
    world.expect(state.get("p_002") is True, "gallery view matches the final toggle")


def _malformed_prober(world: World) -> None:
    world.request_otp(intent="request a code")
    for junk in ("", "12", "abcdef", "1234567"):
        s = world.verify(junk, intent=f"submit a malformed code {junk!r}")
        world.expect(s.status == 401, f"malformed code {junk!r} rejected (not 5xx)")

    s = world.get_gallery(token=None, intent="open gallery with no token")
    world.expect(s.status == 401, "missing token is rejected")

    world.verify(world.current_code(), intent="authenticate properly")
    for bad_photo in ("p_999", "'; DROP TABLE photos;--", "", "p_001‹unicode›"):
        s = world.favourite(bad_photo, intent=f"favorite a bogus photo {bad_photo!r}")
        world.expect(s.status == 404, f"bogus photo {bad_photo!r} -> 404, never a crash")

    structural = sum(len(step.violations) for step in world.transcript)
    world.expect(structural == 0, "no contract invariant was ever violated")
