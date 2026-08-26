from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from .evaluators import evaluate_all
from .models import CaseResult, ExpectationResult, SuiteResult
from .providers import Provider
from .redaction import redact
from .suite import SuiteError, render_case, suite_digest


def run_suite(data: dict[str, Any], provider: Provider, max_workers: int = 4) -> SuiteResult:
    if not 1 <= max_workers <= 32:
        raise ValueError("max_workers must be between 1 and 32")
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    defaults = data.get("defaults", {})

    def run_one(index: int, raw_case: dict[str, Any]) -> tuple[int, CaseResult]:
        try:
            case = render_case(raw_case, defaults)
            response = provider.complete(case)
            checks = evaluate_all(response.text, case.expectations)
            return index, CaseResult(
                id=case.id,
                passed=all(check.passed for check in checks),
                prompt=redact(case.prompt),
                response=redact(response.text),
                latency_ms=response.latency_ms,
                expectations=checks,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                model=response.model,
            )
        except Exception as exc:
            case_id = str(raw_case.get("id", f"case-{index}"))
            prompt = str(raw_case.get("prompt", ""))
            check = ExpectationResult(False, "provider_or_suite", f"{type(exc).__name__}: {exc}")
            return index, CaseResult(
                id=case_id,
                passed=False,
                prompt=redact(prompt),
                response="",
                latency_ms=0,
                expectations=[check],
                error=check.message,
            )

    indexed_results: list[tuple[int, CaseResult]] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(data["cases"]))) as executor:
        futures = [executor.submit(run_one, index, case) for index, case in enumerate(data["cases"])]
        for future in as_completed(futures):
            indexed_results.append(future.result())
    cases = [result for _, result in sorted(indexed_results, key=lambda item: item[0])]
    passed_count = sum(case.passed for case in cases)
    return SuiteResult(
        schema_version=1,
        suite=data["name"],
        suite_digest=suite_digest(data),
        provider_type=provider.provider_type,
        started_at=started_at,
        duration_ms=(time.perf_counter() - started) * 1000,
        passed=passed_count == len(cases),
        summary={"total": len(cases), "passed": passed_count, "failed": len(cases) - passed_count},
        cases=cases,
    )

