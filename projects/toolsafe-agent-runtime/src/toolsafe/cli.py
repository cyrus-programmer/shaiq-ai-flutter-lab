from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import MemoryAuditSink
from .demo import registry
from .models import RuntimePolicy
from .provider import ScriptedProvider
from .runtime import AgentRuntime


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="toolsafe", description="Policy-enforced agent tool calling")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run a deterministic scripted agent")
    run.add_argument("--script", type=Path, required=True)
    run.add_argument("--message", required=True)
    run.add_argument("--audit", type=Path)
    run.add_argument("--max-steps", type=int, default=8)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        script = json.loads(args.script.read_text(encoding="utf-8"))
        responses = script.get("responses")
        if not isinstance(responses, list) or not responses:
            raise ValueError("script requires a non-empty responses list")
        audit = MemoryAuditSink()
        runtime = AgentRuntime(ScriptedProvider(responses), registry(),
                               policy=RuntimePolicy(max_steps=args.max_steps,
                                                    max_tool_calls=min(5, args.max_steps)),
                               audit=audit)
        result = runtime.run(args.message, system=script.get("system", "Use only supplied tools."))
        output = {"status": result.status, "answer": result.answer, "steps": result.steps,
                  "tool_calls": result.tool_calls, "error": result.error}
        print(json.dumps(output, ensure_ascii=False))
        if args.audit:
            args.audit.parent.mkdir(parents=True, exist_ok=True)
            args.audit.write_text(json.dumps([event.to_dict() for event in audit.events], indent=2),
                                  encoding="utf-8")
        return 0 if result.status == "completed" else 2
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"toolsafe: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
