from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
TOKEN = re.compile(r"\b(?:sk|pk|api|token)[-_][A-Za-z0-9_-]{8,}\b", re.IGNORECASE)
SENSITIVE_KEYS = {"password", "secret", "token", "access_token", "refresh_token", "authorization"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.casefold() in SENSITIVE_KEYS else redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        result = EMAIL.sub("[EMAIL]", value)
        result = PHONE.sub("[PHONE]", result)
        return TOKEN.sub("[TOKEN]", result)
    return value


@dataclass(frozen=True)
class AuditEvent:
    kind: str
    call_id: str | None
    tool: str | None
    detail: Any
    created_at: str

    @classmethod
    def create(cls, kind: str, *, call_id: str | None = None,
               tool: str | None = None, detail: Any = None) -> "AuditEvent":
        return cls(kind, call_id, tool, redact(detail), datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None: ...


class MemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)
