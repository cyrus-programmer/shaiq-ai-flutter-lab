from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")
INJECTION_PATTERNS = (
    re.compile(r"ignore (?:all |any )?(?:previous|prior|above) instructions", re.I),
    re.compile(r"(?:reveal|show|print|repeat) (?:the )?(?:system|developer) prompt", re.I),
    re.compile(r"you are now (?:a|an|the) ", re.I),
    re.compile(r"override (?:your|the) (?:rules|instructions)", re.I),
)


def redact_pii(text: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    redacted, emails = EMAIL_RE.subn("[EMAIL_REDACTED]", text)
    if emails:
        flags.append("email_redacted")
    redacted, phones = PHONE_RE.subn("[PHONE_REDACTED]", redacted)
    if phones:
        flags.append("phone_redacted")
    return redacted, flags


def has_prompt_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)

