# AI Synthetic-Persona Test Suite

Contract testing for the gallery API, driven by **synthetic users** instead of
hand-written scenarios. Each *persona* has a goal and quirks; whatever it does,
a set of **invariants** must hold. The point: catch contract violations a fixed
script would miss, and read like the system's behavior under real humans.

```
make personas          # in-process, deterministic, no key needed
make test-personas     # pytest the framework itself
```

## The personas

| Persona | What they stress |
|---|---|
| Anna, the happy bride | the golden path + favorites persistence |
| Bob, all thumbs | wrong codes are rejected, no lockout, recovery |
| Pat, the procrastinator | a rotated-away code dies; recovery works |
| Nick, the nosy one | a token never crosses galleries (read **and** write) |
| Iris, can't decide | favorite-toggle parity == server truth |
| Sam, the prober | junk input is never a 5xx; always the error envelope |

## Invariants (enforced on every response)

- **no_5xx** — the server never 500s, whatever the input.
- **documented_status** — every status is one the contract documents.
- **error_envelope** — every 401/404 body is exactly `{"error": <code>}` with a
  code from the documented enum.

Plus per-persona, goal-level expectations (e.g. "all three favorites persist").
A non-zero exit means an invariant or expectation broke.

## Two policies

**Deterministic** (default): seeded, reproducible behavior models. No network
egress, no API key — this is what CI runs.

**Live** (opt-in): with `ANTHROPIC_API_KEY` set,

```
make install                       # installs the optional `ai` extra (anthropic SDK)
cd ai-testing && ../backend/.venv/bin/python -m persona_suite --live
```

- Claude **role-plays** each persona, choosing the next API action via
  constrained tool-use (it has to read the code off the "terminal" and submit
  it, just like a person) — an LLM-driven fuzzer with human intent.
- A second Claude call acts as an **LLM judge**, scoring each journey for
  contract correctness and UX humaneness and writing notes into the report.

`--judge` runs the deterministic journeys but adds the LLM judge.
`--base-url URL --db-path FILE` points the suite at a running backend over HTTP.
Override the model with `--model` or `ANTHROPIC_MODEL`.

## Output

A console summary plus `reports/personas.html` (a self-contained, shareable
report with every journey, status, and check) and `reports/personas.json`.

## How it's wired

```
persona_suite/
  personas.py      persona catalogue (data + LLM-facing blurbs)
  client.py        the "hands": httpx over the API; in-process or live HTTP
  world.py         executes actions, records the transcript, checks invariants
  deterministic.py seeded per-persona journeys
  llm.py           optional Claude policy + judge (tool-use, structured verdicts)
  report.py        console / JSON / HTML
  __main__.py      CLI
```
