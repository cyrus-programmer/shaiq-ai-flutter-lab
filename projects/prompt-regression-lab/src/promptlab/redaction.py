from __future__ import annotations

import os
import re

PATTERNS = (
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL_REDACTED]"),
    (re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)"), "[PHONE_REDACTED]"),
    (re.compile(r"\b(?:sk|pk|rk|api)[-_][A-Za-z0-9_-]{12,}\b", re.I), "[API_KEY_REDACTED]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{8,}=*"), "Bearer [TOKEN_REDACTED]"),
)


def redact(text: str, extra_values: list[str] | None = None) -> str:
    result = text
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    values = extra_values
    if values is None:
        values = [value.strip() for value in os.getenv("PROMPTLAB_REDACT_VALUES", "").split(",") if value.strip()]
    for value in sorted(values, key=len, reverse=True):
        result = result.replace(value, "[VALUE_REDACTED]")
    return result

