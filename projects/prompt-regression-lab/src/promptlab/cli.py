from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .providers import ProviderError, build_provider
from .reports import compare_results, load_result, write_json, write_junit, write_markdown
from .runner import run_suite
from .suite import SuiteError, load_suite


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="promptlab", description="Prompt regression tests and release gates")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run an evaluation suite")
    run.add_argument("suite", type=Path)
    run.add_argument("--output", type=Path)
    run.add_argument("--markdown", type=Path)
    run.add_argument("--junit", type=Path)
    run.add_argument("--workers", type=int, default=4)
    validate = commands.add_parser("validate", help="Validate a suite without provider calls")
    validate.add_argument("suite", type=Path)
    compare = commands.add_parser("compare", help="Compare candidate results with a baseline")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument("--max-regressions", type=int, default=0)
    compare.add_argument("--max-latency-increase-pct", type=float)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            suite = load_suite(args.suite)
            print(json.dumps({"valid": True, "suite": suite["name"], "cases": len(suite["cases"])}))
            return 0
        if args.command == "run":
            suite = load_suite(args.suite)
            provider = build_provider(suite["provider"])
            result = run_suite(suite, provider, max_workers=args.workers)
            if args.output:
                write_json(result, args.output)
            if args.markdown:
                write_markdown(result, args.markdown)
            if args.junit:
                write_junit(result, args.junit)
            print(json.dumps({"suite": result.suite, "passed": result.passed, "summary": result.summary}))
            return 0 if result.passed else 2
        if args.command == "compare":
            if args.max_regressions < 0:
                raise ValueError("max-regressions must be zero or greater")
            comparison = compare_results(
                load_result(args.baseline), load_result(args.candidate),
                max_regressions=args.max_regressions,
                max_latency_increase_pct=args.max_latency_increase_pct,
            )
            print(json.dumps(comparison, indent=2))
            return 0 if comparison["passed"] else 2
    except (SuiteError, ProviderError, ValueError) as exc:
        print(f"promptlab: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
