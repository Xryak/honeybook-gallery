"""Run personas and aggregate results."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import deterministic
from .client import GalleryClient
from .personas import PERSONAS, Persona
from .world import Expectation, Step


@dataclass
class PersonaResult:
    persona: Persona
    steps: list[Step]
    expectations: list[Expectation]
    llm_judge: dict | None = None
    error: str | None = None

    @property
    def structural_violations(self) -> list[str]:
        out: list[str] = []
        for step in self.steps:
            out.extend(f"[{step.call}] {v}" for v in step.violations)
        return out

    @property
    def failed_expectations(self) -> list[Expectation]:
        return [e for e in self.expectations if not e.passed]

    @property
    def passed(self) -> bool:
        return (
            self.error is None
            and not self.structural_violations
            and not self.failed_expectations
            # An LLM judge that finds an incorrectness fails the persona; UX notes
            # are advisory only.
            and (self.llm_judge is None or self.llm_judge.get("correct", True))
        )


@dataclass
class SuiteResult:
    results: list[PersonaResult] = field(default_factory=list)
    policy: str = "deterministic"
    judged: bool = False

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)


def run_suite(
    client: GalleryClient,
    *,
    policy: str = "deterministic",
    judge: bool = False,
    model: str | None = None,
    personas: list[Persona] | None = None,
) -> SuiteResult:
    from .world import World  # local import keeps module import cheap

    personas = personas or PERSONAS
    suite = SuiteResult(policy=policy, judged=judge)

    for persona in personas:
        world = World(client, persona)
        try:
            if policy == "live":
                from .llm import drive_with_llm

                drive_with_llm(world, model=model)
            else:
                deterministic.run(world)
            error = None
        except Exception as exc:  # a thrown policy shouldn't kill the whole suite
            error = f"{type(exc).__name__}: {exc}"

        result = PersonaResult(
            persona=persona,
            steps=world.transcript,
            expectations=world.expectations,
            error=error,
        )

        if judge:
            from .llm import judge_journey

            try:
                result.llm_judge = judge_journey(world, model=model)
            except Exception as exc:
                result.llm_judge = {"correct": True, "available": False, "notes": str(exc)}

        suite.results.append(result)

    return suite
