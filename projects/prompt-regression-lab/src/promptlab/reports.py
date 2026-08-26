from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .models import SuiteResult


def write_json(result: SuiteResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_markdown(result: SuiteResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"# {result.suite} evaluation", "", f"**Status:** {status}", "",
        f"Cases: {result.summary['passed']} passed, {result.summary['failed']} failed, {result.summary['total']} total.",
        "", "| Case | Status | Latency | Model |", "| --- | --- | ---: | --- |",
    ]
    for case in result.cases:
        lines.append(f"| `{case.id}` | {'PASS' if case.passed else 'FAIL'} | {case.latency_ms:.2f} ms | {case.model or 'n/a'} |")
    for case in result.cases:
        if case.passed:
            continue
        lines.extend(["", f"## {case.id}", ""])
        for check in case.expectations:
            if not check.passed:
                lines.append(f"- `{check.expectation_type}`: {check.message}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_junit(result: SuiteResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suite = ET.Element("testsuite", {
        "name": result.suite,
        "tests": str(result.summary["total"]),
        "failures": str(result.summary["failed"]),
        "time": f"{result.duration_ms / 1000:.6f}",
    })
    for case in result.cases:
        testcase = ET.SubElement(suite, "testcase", {
            "name": case.id,
            "classname": result.suite,
            "time": f"{case.latency_ms / 1000:.6f}",
        })
        if not case.passed:
            messages = "; ".join(check.message for check in case.expectations if not check.passed)
            failure = ET.SubElement(testcase, "failure", {"message": messages})
            failure.text = messages
    tree = ET.ElementTree(suite)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n")


def load_result(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load result {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError(f"Result {path} has an invalid shape")
    return data


def compare_results(
    baseline: dict[str, Any], candidate: dict[str, Any], *, max_regressions: int = 0,
    max_latency_increase_pct: float | None = None,
) -> dict[str, Any]:
    baseline_suite = baseline.get("suite")
    candidate_suite = candidate.get("suite")
    if baseline_suite and candidate_suite and baseline_suite != candidate_suite:
        raise ValueError(f"Cannot compare different suites: {baseline_suite} and {candidate_suite}")
    base_cases = {case["id"]: case for case in baseline["cases"]}
    candidate_cases = {case["id"]: case for case in candidate["cases"]}
    added = sorted(candidate_cases.keys() - base_cases.keys())
    missing = sorted(base_cases.keys() - candidate_cases.keys())
    regressed = sorted(
        case_id for case_id in base_cases.keys() & candidate_cases.keys()
        if base_cases[case_id].get("passed") and not candidate_cases[case_id].get("passed")
    )
    improved = sorted(
        case_id for case_id in base_cases.keys() & candidate_cases.keys()
        if not base_cases[case_id].get("passed") and candidate_cases[case_id].get("passed")
    )
    unchanged = sorted((base_cases.keys() & candidate_cases.keys()) - set(regressed) - set(improved))
    latency_violations: list[str] = []
    if max_latency_increase_pct is not None:
        for case_id in base_cases.keys() & candidate_cases.keys():
            before = float(base_cases[case_id].get("latency_ms", 0))
            after = float(candidate_cases[case_id].get("latency_ms", 0))
            if before > 0 and ((after - before) / before * 100) > max_latency_increase_pct:
                latency_violations.append(case_id)
    regression_count = len(regressed) + len(missing)
    passed = regression_count <= max_regressions and not latency_violations
    return {
        "passed": passed,
        "suite": candidate_suite or baseline_suite,
        "regression_count": regression_count,
        "regressed": regressed,
        "missing": missing,
        "improved": improved,
        "added": added,
        "unchanged": unchanged,
        "latency_violations": sorted(latency_violations),
    }
