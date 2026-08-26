from __future__ import annotations

import json
import re
from typing import Any

from .models import ExpectationResult


def _text_pair(actual: str, expected: str, case_sensitive: bool) -> tuple[str, str]:
    if case_sensitive:
        return actual, expected
    return actual.casefold(), expected.casefold()


def _json_path(document: Any, path: str) -> Any:
    current = document
    for part in path.split(".") if path else []:
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise KeyError(path) from exc
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(path)
    return current


def _matches_type(value: Any, expected: str) -> bool:
    checks = {
        "string": lambda item: isinstance(item, str),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "null": lambda item: item is None,
    }
    if expected not in checks:
        raise ValueError(f"Unsupported JSON type: {expected}")
    return checks[expected](value)


def evaluate(response: str, expectation: dict[str, Any]) -> ExpectationResult:
    kind = expectation["type"]
    case_sensitive = expectation.get("case_sensitive", True)
    try:
        if kind == "exact":
            actual, wanted = _text_pair(response.strip(), str(expectation["value"]).strip(), case_sensitive)
            passed = actual == wanted
            message = "exact output matched" if passed else "exact output did not match"
        elif kind in {"contains", "not_contains"}:
            actual, wanted = _text_pair(response, str(expectation["value"]), case_sensitive)
            contains = wanted in actual
            passed = contains if kind == "contains" else not contains
            message = f"output {'contains' if contains else 'does not contain'} expected text"
        elif kind == "regex":
            flags = 0 if case_sensitive else re.IGNORECASE
            passed = re.search(str(expectation["pattern"]), response, flags) is not None
            message = "regular expression matched" if passed else "regular expression did not match"
        elif kind == "json_path":
            document = json.loads(response)
            value = _json_path(document, str(expectation.get("path", "")))
            checks: list[bool] = []
            descriptions: list[str] = []
            if "equals" in expectation:
                checks.append(value == expectation["equals"])
                descriptions.append("value equality")
            if "value_type" in expectation:
                checks.append(_matches_type(value, expectation["value_type"]))
                descriptions.append("type")
            if not checks:
                checks.append(True)
                descriptions.append("path existence")
            passed = all(checks)
            message = f"JSON path {expectation.get('path', '<root>')} {'passed' if passed else 'failed'} {', '.join(descriptions)}"
        else:
            raise ValueError(f"Unsupported expectation: {kind}")
        return ExpectationResult(passed, kind, message)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, re.error) as exc:
        return ExpectationResult(False, kind, f"evaluation error: {type(exc).__name__}: {exc}")


def evaluate_all(response: str, expectations: list[dict[str, Any]]) -> list[ExpectationResult]:
    return [evaluate(response, expectation) for expectation in expectations]
