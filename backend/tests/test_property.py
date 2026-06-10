"""Property-based tests (Hypothesis).

These assert invariants over wide input spaces rather than single examples:
codes are always well-formed, wrong codes never authenticate and never 500,
arbitrary photo ids degrade to 404 (never a crash), and toggling N times lands
on the parity-correct favorite state.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

GALLERIES = st.sampled_from(["g_001", "g_002"])
# Suppress the function-scoped-fixture health check: the TestClient/DB is reused
# across a test's generated examples on purpose (each example is independent).
PROP = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@PROP
@given(gallery=GALLERIES)
def test_issued_code_is_always_six_digits(app_client, latest_code, gallery):
    r = app_client.post(f"/api/galleries/{gallery}/otp")
    assert r.status_code == 200
    code = latest_code(gallery)
    assert len(code) == 6 and code.isdigit()


@PROP
@given(candidate=st.from_regex(r"[0-9]{6}", fullmatch=True))
def test_verify_discriminates_every_six_digit_input(app_client, latest_code, candidate):
    """For any 6-digit input: exactly the issued code 200s, everything else
    401s. No input ever yields a 5xx."""
    app_client.post("/api/galleries/g_001/otp")
    real = latest_code("g_001")

    r = app_client.post("/api/galleries/g_001/verify", json={"code": candidate})
    if candidate == real:
        assert r.status_code == 200
        assert "token" in r.json()
    else:
        assert r.status_code == 401
        assert r.json() == {"error": "invalid_code"}


@PROP
@given(code=st.text(max_size=12))
def test_verify_never_500s_on_arbitrary_text(app_client, latest_code, code):
    """Arbitrary (possibly malformed) code strings are rejected, never crash."""
    app_client.post("/api/galleries/g_001/otp")
    real = latest_code("g_001")
    r = app_client.post("/api/galleries/g_001/verify", json={"code": code})
    assert r.status_code in (200, 401)
    if r.status_code == 200:
        assert code == real  # only the exact code can succeed


@PROP
@given(photo_id=st.text(max_size=24))
def test_arbitrary_photo_id_is_404_not_500(app_client, mint_token, photo_id):
    """Favoriting an arbitrary photo id (SQL-ish, unicode, empty) is a clean
    404 unless it's a real photo of this gallery — never a server error."""
    token = mint_token(app_client, "g_001")
    real_photos = {f"p_{n:03d}" for n in range(1, 11)}
    r = app_client.post(
        "/api/galleries/g_001/favourite",
        json={"photo_id": photo_id},
        headers=_auth(token),
    )
    if photo_id in real_photos:
        assert r.status_code == 200
    else:
        assert r.status_code == 404
        assert r.json() == {"error": "not_found"}


@PROP
@given(clicks=st.integers(min_value=0, max_value=9))
def test_favorite_toggle_parity(app_client, mint_token, clicks):
    """N toggles -> favorite iff N is odd; the GET view agrees with the toggle."""
    token = mint_token(app_client, "g_001")
    last_state = False
    for _ in range(clicks):
        r = app_client.post(
            "/api/galleries/g_001/favourite",
            json={"photo_id": "p_001"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        last_state = r.json()["is_favorite"]

    assert last_state == (clicks % 2 == 1)

    r = app_client.get("/api/galleries/g_001", headers=_auth(token))
    photos = {p["id"]: p for p in r.json()["photos"]}
    assert photos["p_001"]["is_favorite"] == (clicks % 2 == 1)


def test_minted_tokens_are_unique(app_client, mint_token):
    """Many mints never collide (secrets.token_urlsafe entropy)."""
    tokens = {mint_token(app_client, "g_001") for _ in range(25)}
    assert len(tokens) == 25
