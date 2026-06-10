"""Synthetic-persona test suite for the Honeybook gallery API.

Instead of hand-writing scenarios, we define *personas* — synthetic users with
goals and quirks — and let each one drive the real API. Whatever they do, a set
of contract *invariants* must hold (never a 5xx, every error is the documented
envelope, a token never crosses galleries, favorites stay consistent, …).

Two policies decide what a persona does next:

* **deterministic** (default) — seeded, reproducible behavior models. No network
  egress, no API key, runs in CI. This is model-based testing with
  human-flavored journeys.
* **live** (opt-in, needs ANTHROPIC_API_KEY) — Claude role-plays the persona,
  choosing actions via constrained tool-use, and a second Claude call acts as an
  LLM judge scoring correctness and UX humaneness.

Entry point: ``python -m persona_suite`` (see ``__main__``).
"""

from .personas import PERSONAS, Persona
from .runner import PersonaResult, run_suite
from .world import Step, World

__all__ = ["PERSONAS", "Persona", "PersonaResult", "Step", "World", "run_suite"]
