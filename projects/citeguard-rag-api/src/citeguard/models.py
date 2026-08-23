from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    title: str
    text: str
    position: int
    unsafe: bool = False


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float

    def citation_dict(self) -> dict[str, Any]:
        return {
            "id": self.chunk.id,
            "source": self.chunk.source,
            "title": self.chunk.title,
            "score": round(self.score, 4),
            "text": self.chunk.text,
        }


@dataclass
class QueryResult:
    answer: str
    citations: list[dict[str, Any]]
    confidence: float
    abstained: bool
    mode: str
    safety_flags: list[str] = field(default_factory=list)
    request_id: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = round(self.confidence, 4)
        data["latency_ms"] = round(self.latency_ms, 2)
        return data

