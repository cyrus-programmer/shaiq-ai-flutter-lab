from __future__ import annotations

import hashlib
import json
import string
from pathlib import Path
from typing import Any

from .models import CaseDefinition


class SuiteError(ValueError):
    pass


def load_suite(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError as exc:
        raise SuiteError(f"Could not read suite: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SuiteError(f"Suite is not valid JSON: {exc}") from exc
    validate_suite(data)
    return data


def validate_suite(data: Any) -> None:
    if not isinstance(data, dict):
        raise SuiteError("Suite must be a JSON object")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise SuiteError("Suite name must be a non-empty string")
    provider = data.get("provider")
    if not isinstance(provider, dict) or provider.get("type") not in {"fixture", "openai_compatible"}:
        raise SuiteError("provider.type must be fixture or openai_compatible")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SuiteError("Suite must contain at least one case")
    ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise SuiteError(f"Case {index} must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise SuiteError(f"Case {index} requires a non-empty id")
        if case_id in ids:
            raise SuiteError(f"Duplicate case id: {case_id}")
        ids.add(case_id)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise SuiteError(f"Case {case_id} requires a prompt")
        if not isinstance(case.get("variables", {}), dict):
            raise SuiteError(f"Case {case_id} variables must be an object")
        expectations = case.get("expectations")
        if not isinstance(expectations, list) or not expectations:
            raise SuiteError(f"Case {case_id} requires expectations")
        for expectation in expectations:
            if not isinstance(expectation, dict) or expectation.get("type") not in {
                "exact", "contains", "not_contains", "regex", "json_path"
            }:
                raise SuiteError(f"Case {case_id} has an unsupported expectation")
            kind = expectation["type"]
            if kind in {"exact", "contains", "not_contains"} and not isinstance(expectation.get("value"), str):
                raise SuiteError(f"Case {case_id} {kind} expectation requires a string value")
            if kind == "regex" and not isinstance(expectation.get("pattern"), str):
                raise SuiteError(f"Case {case_id} regex expectation requires a pattern")
            if kind == "json_path":
                if not isinstance(expectation.get("path", ""), str):
                    raise SuiteError(f"Case {case_id} json_path path must be a string")
                if "value_type" in expectation and expectation["value_type"] not in {
                    "string", "number", "integer", "boolean", "object", "array", "null"
                }:
                    raise SuiteError(f"Case {case_id} json_path has an unsupported value_type")
    if provider["type"] == "fixture":
        responses = provider.get("responses")
        if not isinstance(responses, dict):
            raise SuiteError("Fixture provider requires a responses object")
        missing = ids - responses.keys()
        if missing:
            raise SuiteError(f"Fixture responses missing cases: {', '.join(sorted(missing))}")


def render_case(case: dict[str, Any], defaults: dict[str, Any] | None = None) -> CaseDefinition:
    defaults = defaults or {}
    prompt = case["prompt"]
    variables = case.get("variables", {})
    fields = {
        field_name for _, field_name, _, _ in string.Formatter().parse(prompt) if field_name
    }
    missing = fields - variables.keys()
    extra = variables.keys() - fields
    if missing:
        raise SuiteError(f"Case {case['id']} missing prompt variables: {', '.join(sorted(missing))}")
    if extra:
        raise SuiteError(f"Case {case['id']} has unused prompt variables: {', '.join(sorted(extra))}")
    try:
        rendered = prompt.format_map(variables)
    except (KeyError, ValueError) as exc:
        raise SuiteError(f"Case {case['id']} prompt rendering failed: {exc}") from exc
    temperature = case.get("temperature", defaults.get("temperature", 0))
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool) or not 0 <= temperature <= 2:
        raise SuiteError(f"Case {case['id']} temperature must be between 0 and 2")
    system = case.get("system", defaults.get("system", ""))
    if not isinstance(system, str):
        raise SuiteError(f"Case {case['id']} system prompt must be a string")
    return CaseDefinition(
        id=case["id"],
        prompt=rendered,
        variables=variables,
        expectations=case["expectations"],
        system=system,
        temperature=float(temperature),
    )


def suite_digest(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
