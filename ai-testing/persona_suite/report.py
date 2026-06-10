"""Render suite results: console summary, JSON, and a self-contained HTML report."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .runner import PersonaResult, SuiteResult

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"


def console_summary(suite: SuiteResult) -> str:
    lines = [
        "",
        f"Synthetic-persona suite  ·  policy={suite.policy}"
        + ("  ·  LLM judge=on" if suite.judged else ""),
        "─" * 60,
    ]
    for r in suite.results:
        mark = f"{GREEN}PASS{RESET}" if r.passed else f"{RED}FAIL{RESET}"
        passed_exp = sum(1 for e in r.expectations if e.passed)
        lines.append(
            f"  {mark}  {r.persona.name:<28} "
            f"{len(r.steps):>2} steps · {passed_exp}/{len(r.expectations)} checks"
        )
        for e in r.failed_expectations:
            lines.append(f"        {RED}✗ {e.description}{RESET}")
        for v in r.structural_violations:
            lines.append(f"        {RED}✗ invariant: {v}{RESET}")
        if r.error:
            lines.append(f"        {RED}✗ error: {r.error}{RESET}")
        if r.llm_judge and r.llm_judge.get("available"):
            j = r.llm_judge
            lines.append(
                f"        {DIM}judge: correct={j.get('correct')} "
                f"ux={j.get('ux_score')}/5 — {j.get('notes', '')[:80]}{RESET}"
            )
    lines.append("─" * 60)
    total = len(suite.results)
    ok = sum(1 for r in suite.results if r.passed)
    verdict = f"{GREEN}ALL PASS{RESET}" if suite.passed else f"{RED}FAILURES{RESET}"
    lines.append(f"  {ok}/{total} personas passed   {verdict}")
    lines.append("")
    return "\n".join(lines)


def to_dict(suite: SuiteResult) -> dict:
    def persona_dict(r: PersonaResult) -> dict:
        return {
            "id": r.persona.id,
            "name": r.persona.name,
            "gallery": r.persona.gallery,
            "passed": r.passed,
            "error": r.error,
            "steps": [
                {
                    "intent": s.intent,
                    "call": s.call,
                    "status": s.status,
                    "body": s.body,
                    "violations": s.violations,
                }
                for s in r.steps
            ],
            "expectations": [
                {"description": e.description, "passed": e.passed} for e in r.expectations
            ],
            "structural_violations": r.structural_violations,
            "llm_judge": r.llm_judge,
        }

    return {
        "policy": suite.policy,
        "judged": suite.judged,
        "passed": suite.passed,
        "personas": [persona_dict(r) for r in suite.results],
    }


def write_json(suite: SuiteResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(suite), indent=2, default=str))


def _badge(ok: bool) -> str:
    cls = "ok" if ok else "bad"
    text = "PASS" if ok else "FAIL"
    return f'<span class="badge {cls}">{text}</span>'


def write_html(suite: SuiteResult, path: Path) -> None:
    cards = []
    for r in suite.results:
        rows = "".join(
            f"<tr class='{'sv' if s.violations else ''}'>"
            f"<td>{i}</td><td>{html.escape(s.intent)}</td>"
            f"<td><code>{html.escape(s.call)}</code></td>"
            f"<td class='st st{s.status // 100}'>{s.status}</td>"
            f"<td><code>{html.escape(json.dumps(s.body, default=str))[:160]}</code></td>"
            f"</tr>"
            for i, s in enumerate(r.steps, 1)
        )
        checks = "".join(
            f"<li class='{'ok' if e.passed else 'bad'}'>"
            f"{'✓' if e.passed else '✗'} {html.escape(e.description)}</li>"
            for e in r.expectations
        )
        judge_html = ""
        if r.llm_judge and r.llm_judge.get("available"):
            j = r.llm_judge
            concerns = "".join(f"<li>{html.escape(str(c))}</li>" for c in j.get("concerns", []))
            judge_html = (
                "<div class='judge'><b>🧑‍⚖️ Claude judge</b> — "
                f"correct={j.get('correct')} · UX {j.get('ux_score')}/5<br>"
                f"<i>{html.escape(str(j.get('notes', '')))}</i>"
                + (f"<ul>{concerns}</ul>" if concerns else "")
                + "</div>"
            )
        cards.append(
            f"""
            <section class="card {'pass' if r.passed else 'fail'}">
              <h2>{_badge(r.passed)} {html.escape(r.persona.name)}
                <small>{html.escape(r.persona.gallery)}</small></h2>
              <p class="blurb">{html.escape(r.persona.blurb)}</p>
              <table><thead><tr><th>#</th><th>intent</th><th>call</th>
                <th>status</th><th>response</th></tr></thead>
                <tbody>{rows}</tbody></table>
              <ul class="checks">{checks}</ul>
              {judge_html}
            </section>"""
        )

    ok = sum(1 for r in suite.results if r.passed)
    head = (
        f"<header><h1>Synthetic Persona Test Report</h1>"
        f"<p>{ok}/{len(suite.results)} personas passed · policy "
        f"<b>{suite.policy}</b>{' · LLM judge on' if suite.judged else ''}</p></header>"
    )
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Persona Test Report</title><style>{_CSS}</style></head>
<body>{head}{''.join(cards)}</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc)


_CSS = """
:root{font-family:system-ui,-apple-system,sans-serif;color:#1a1a1a}
body{max-width:60rem;margin:2rem auto;padding:0 1rem;background:#fafafa}
header h1{font-weight:300;margin-bottom:.2rem}
.card{background:#fff;border:1px solid #eee;border-left:4px solid #ccc;border-radius:10px;
 padding:1rem 1.25rem;margin:1rem 0;box-shadow:0 1px 2px rgba(0,0,0,.04)}
.card.pass{border-left-color:#2e9b57}.card.fail{border-left-color:#e0245e}
.card h2{font-size:1.15rem;font-weight:500;margin:.2rem 0 .4rem}
.card h2 small{color:#888;font-weight:400;font-size:.8rem;margin-left:.4rem}
.blurb{color:#555;font-size:.9rem;margin:.2rem 0 .8rem}
.badge{font-size:.7rem;padding:.1rem .45rem;border-radius:4px;color:#fff;vertical-align:middle}
.badge.ok{background:#2e9b57}.badge.bad{background:#e0245e}
table{width:100%;border-collapse:collapse;font-size:.8rem;margin:.4rem 0}
th{text-align:left;color:#888;font-weight:500;border-bottom:1px solid #eee;padding:.25rem .4rem}
td{padding:.25rem .4rem;border-bottom:1px solid #f4f4f4;vertical-align:top}
tr.sv{background:#fff4f6}
code{font-family:ui-monospace,Menlo,monospace;font-size:.78rem;color:#333}
.st{font-weight:600;text-align:center}.st2{color:#2e9b57}.st4{color:#c47f17}.st5{color:#e0245e}
.checks{list-style:none;padding:0;margin:.5rem 0;font-size:.82rem;display:grid;
 grid-template-columns:1fr 1fr;gap:.1rem .8rem}
.checks li.ok{color:#2e7d46}.checks li.bad{color:#e0245e;font-weight:600}
.judge{margin-top:.6rem;padding:.6rem .8rem;background:#f6f8ff;border-radius:8px;font-size:.85rem}
"""
