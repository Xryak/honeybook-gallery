"""CLI entry point for the synthetic-persona suite.

    python -m persona_suite                      # in-process, deterministic
    python -m persona_suite --live               # Claude drives + judges (needs key)
    python -m persona_suite --judge              # deterministic journeys, LLM-judged
    python -m persona_suite --base-url URL --db-path PATH   # against a live backend

Exit code is non-zero if any persona fails an invariant or expectation, so it
drops straight into CI / Make.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import report
from .client import GalleryClient
from .runner import run_suite

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="persona_suite", description=__doc__)
    parser.add_argument("--base-url", help="Run against a live backend at this URL.")
    parser.add_argument(
        "--db-path",
        help="Backend SQLite file to read OTP codes from (required with --base-url).",
    )
    parser.add_argument(
        "--live", action="store_true", help="Let Claude role-play personas + judge."
    )
    parser.add_argument(
        "--judge", action="store_true", help="LLM-judge deterministic journeys."
    )
    parser.add_argument("--model", help="Override the Claude model id.")
    parser.add_argument(
        "--report-dir", default=str(REPORTS), help="Where to write html/json reports."
    )
    args = parser.parse_args(argv)

    if args.base_url:
        if not args.db_path:
            parser.error("--base-url requires --db-path (to read OTP codes).")
        client = GalleryClient.over_http(args.base_url, args.db_path)
    else:
        client = GalleryClient.in_process()

    policy = "live" if args.live else "deterministic"
    judge = args.live or args.judge

    if (args.live or args.judge):
        from .llm import live_available

        if not live_available():
            print(
                "  [!] live/judge requested but anthropic SDK + ANTHROPIC_API_KEY "
                "not available — falling back to deterministic, unjudged.\n"
            )
            policy, judge = "deterministic", False

    try:
        suite = run_suite(client, policy=policy, judge=judge, model=args.model)
    finally:
        client.close()

    print(report.console_summary(suite))

    report_dir = Path(args.report_dir)
    report.write_html(suite, report_dir / "personas.html")
    report.write_json(suite, report_dir / "personas.json")
    print(f"  report: {report_dir / 'personas.html'}\n")

    return 0 if suite.passed else 1


if __name__ == "__main__":
    sys.exit(main())
