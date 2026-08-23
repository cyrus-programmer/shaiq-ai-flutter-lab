from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str = "0.0.0.0"
    port: int = 8080
    knowledge_dir: Path = Path("knowledge")
    top_k: int = 4
    min_score: float = 0.12
    redact_pii: bool = True
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 20.0

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    @classmethod
    def from_env(cls) -> "Settings":
        top_k = int(os.getenv("CITEGUARD_TOP_K", "4"))
        port = int(os.getenv("CITEGUARD_PORT", "8080"))
        min_score = float(os.getenv("CITEGUARD_MIN_SCORE", "0.12"))
        if not 1 <= top_k <= 10:
            raise ValueError("CITEGUARD_TOP_K must be between 1 and 10")
        if not 1 <= port <= 65535:
            raise ValueError("CITEGUARD_PORT must be between 1 and 65535")
        if not 0 <= min_score <= 1:
            raise ValueError("CITEGUARD_MIN_SCORE must be between 0 and 1")
        return cls(
            host=os.getenv("CITEGUARD_HOST", "0.0.0.0"),
            port=port,
            knowledge_dir=Path(os.getenv("CITEGUARD_KNOWLEDGE_DIR", "knowledge")),
            top_k=top_k,
            min_score=min_score,
            redact_pii=_boolean("CITEGUARD_REDACT_PII", True),
            llm_base_url=os.getenv("CITEGUARD_LLM_BASE_URL"),
            llm_api_key=os.getenv("CITEGUARD_LLM_API_KEY"),
            llm_model=os.getenv("CITEGUARD_LLM_MODEL"),
            llm_timeout_seconds=float(os.getenv("CITEGUARD_LLM_TIMEOUT_SECONDS", "20")),
        )

