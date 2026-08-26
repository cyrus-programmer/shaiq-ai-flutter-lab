from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None


@dataclass(frozen=True)
class ExpectationResult:
    passed: bool
    expectation_type: str
    message: str


@dataclass(frozen=True)
class CaseDefinition:
    id: str
    prompt: str
    variables: dict[str, Any]
    expectations: list[dict[str, Any]]
    system: str = ""
    temperature: float = 0.0


@dataclass
class CaseResult:
    id: str
    passed: bool
    prompt: str
    response: str
    latency_ms: float
    expectations: list[ExpectationResult]
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["latency_ms"] = round(self.latency_ms, 3)
        return data


@dataclass
class SuiteResult:
    schema_version: int
    suite: str
    suite_digest: str
    provider_type: str
    started_at: str
    duration_ms: float
    passed: bool
    summary: dict[str, int]
    cases: list[CaseResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "suite": self.suite,
            "suite_digest": self.suite_digest,
            "provider_type": self.provider_type,
            "started_at": self.started_at,
            "duration_ms": round(self.duration_ms, 3),
            "passed": self.passed,
            "summary": self.summary,
            "cases": [case.to_dict() for case in self.cases],
        }

