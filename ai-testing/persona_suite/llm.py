"""Optional Claude-backed policy + judge.

* :func:`drive_with_llm` lets Claude *role-play* the persona, choosing the next
  API action via constrained tool-use until it decides to finish.
* :func:`judge_journey` asks Claude to score a completed journey for contract
  correctness and UX humaneness, returning structured JSON.

Both require the ``anthropic`` SDK and ``ANTHROPIC_API_KEY``. They raise a clear
RuntimeError otherwise; the runner degrades gracefully.
"""

from __future__ import annotations

import os

from .world import World

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
MAX_TURNS = 14


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise RuntimeError(
            "live mode needs the anthropic SDK — install with `pip install -e ./backend[ai]`"
        ) from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("live mode needs ANTHROPIC_API_KEY in the environment")
    return anthropic.Anthropic()


# --- persona-as-agent -------------------------------------------------------

_POLICY_TOOLS = [
    {"name": "read_terminal", "description": "Read the latest OTP code printed to the backend terminal (what a real user would do).", "input_schema": {"type": "object", "properties": {}}},
    {"name": "request_code", "description": "Ask the system to send/print a fresh OTP code for your gallery.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "verify_code", "description": "Submit a 6-digit code to authenticate.", "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
    {"name": "open_gallery", "description": "Open a gallery (defaults to yours).", "input_schema": {"type": "object", "properties": {"gallery": {"type": "string"}}}},
    {"name": "favorite_photo", "description": "Toggle a photo as favorite.", "input_schema": {"type": "object", "properties": {"photo_id": {"type": "string"}, "gallery": {"type": "string"}}, "required": ["photo_id"]}},
    {"name": "finish", "description": "You are done; summarize what you accomplished.", "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}},
]


def _dispatch(world: World, name: str, args: dict) -> str:
    if name == "read_terminal":
        return f"The terminal shows code: {world.current_code()}"
    if name == "request_code":
        s = world.request_otp(intent="(LLM) request a code")
        return f"status={s.status} body={s.body}"
    if name == "verify_code":
        s = world.verify(args.get("code", ""), intent=f"(LLM) verify {args.get('code')!r}")
        return f"status={s.status} body={s.body}"
    if name == "open_gallery":
        s = world.get_gallery(gallery=args.get("gallery"), intent="(LLM) open gallery")
        return f"status={s.status} body={s.body}"
    if name == "favorite_photo":
        s = world.favourite(
            args.get("photo_id", ""), gallery=args.get("gallery"), intent="(LLM) favorite"
        )
        return f"status={s.status} body={s.body}"
    return "unknown tool"


def drive_with_llm(world: World, *, model: str | None = None) -> None:
    client = _client()
    model = model or DEFAULT_MODEL
    system = (
        "You are a synthetic QA persona exercising a photo-gallery API. Stay in "
        "character and pursue your goal using the tools. To authenticate you must "
        "read the current code from the terminal and submit it. Keep going until "
        "you've achieved (or proven you cannot achieve) your goal, then call "
        "finish. Be efficient — a handful of actions is plenty."
    )
    messages = [
        {
            "role": "user",
            "content": (
                f"Persona: {world.persona.name}\n"
                f"Your gallery: {world.persona.gallery}\n"
                f"Goal & quirks: {world.persona.blurb}\n\n"
                "Begin."
            ),
        }
    ]

    for _ in range(MAX_TURNS):
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=_POLICY_TOOLS,
            tool_choice={"type": "any"},
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        finished = False
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if block.name == "finish":
                finished = True
                continue
            output = _dispatch(world, block.name, dict(block.input or {}))
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": output}
            )
        if finished:
            break
        if not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})

    # Guard against a vacuous PASS: an LLM that calls finish immediately tested
    # nothing, and a result with zero steps + zero expectations would otherwise
    # be reported as passing.
    world.expect(len(world.transcript) > 0, "persona took at least one API action")


# --- LLM judge --------------------------------------------------------------

_VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Record your judgement of the persona's journey.",
    "input_schema": {
        "type": "object",
        "properties": {
            "correct": {
                "type": "boolean",
                "description": "Did the API uphold its documented contract for this persona (right status codes, error envelopes, scoping, favorite consistency)?",
            },
            "ux_score": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "How humane/recoverable was the experience (1 poor, 5 excellent)?",
            },
            "notes": {"type": "string"},
            "concerns": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["correct", "ux_score", "notes"],
    },
}


def _transcript_text(world: World) -> str:
    lines = []
    for i, s in enumerate(world.transcript, 1):
        flag = "" if s.ok else f"  ⚠ {s.violations}"
        lines.append(f"{i}. [{s.intent}] {s.call} -> {s.status} {s.body}{flag}")
    exp = "\n".join(
        f"- [{'ok' if e.passed else 'FAIL'}] {e.description}" for e in world.expectations
    )
    return "JOURNEY:\n" + "\n".join(lines) + "\n\nEXPECTATIONS:\n" + exp


def judge_journey(world: World, *, model: str | None = None) -> dict:
    client = _client()
    model = model or DEFAULT_MODEL
    resp = client.messages.create(
        model=model,
        max_tokens=700,
        system=(
            "You are a meticulous QA reviewer. Given a persona and the exact "
            "sequence of API calls/responses it produced, judge whether the API "
            "honored its documented contract and how humane the experience was. "
            "Call submit_verdict exactly once."
        ),
        tools=[_VERDICT_TOOL],
        tool_choice={"type": "tool", "name": "submit_verdict"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Persona: {world.persona.name}\n{world.persona.blurb}\n\n"
                    f"{_transcript_text(world)}"
                ),
            }
        ],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "submit_verdict":
            verdict = dict(block.input)
            verdict["available"] = True
            return verdict
    return {"correct": True, "available": False, "notes": "no verdict returned"}


def live_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))
