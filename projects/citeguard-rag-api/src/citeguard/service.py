from __future__ import annotations

import re
import time
import uuid
from typing import Protocol

from .models import QueryResult, SearchHit
from .retrieval import BM25Retriever
from .safety import has_prompt_injection, redact_pii


class Generator(Protocol):
    def generate(self, question: str, hits: list[SearchHit]) -> str: ...


class RAGService:
    def __init__(
        self,
        retriever: BM25Retriever,
        *,
        generator: Generator | None = None,
        min_score: float = 0.12,
        redact: bool = True,
    ):
        self.retriever = retriever
        self.generator = generator
        self.min_score = min_score
        self.redact = redact

    def query(self, question: str, top_k: int = 4) -> QueryResult:
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        clean_question = question.strip()
        flags: list[str] = []
        if self.redact:
            clean_question, redaction_flags = redact_pii(clean_question)
            flags.extend(redaction_flags)
        if has_prompt_injection(clean_question):
            flags.append("question_prompt_injection")

        hits = self.retriever.search(clean_question, top_k=top_k)
        if any(hit.chunk.unsafe for hit in hits):
            flags.append("context_prompt_injection")
        safe_hits = [hit for hit in hits if not hit.chunk.unsafe]
        confidence = safe_hits[0].score if safe_hits else 0.0
        if not safe_hits or confidence < self.min_score:
            return self._result(
                "I do not have enough supported information to answer that question.",
                [],
                confidence,
                True,
                "abstained",
                flags,
                request_id,
                started,
            )

        citations = [hit.citation_dict() for hit in safe_hits]
        answer = self._extractive_answer(safe_hits)
        mode = "extractive"
        if self.generator is not None:
            try:
                generated = self.generator.generate(clean_question, safe_hits)
                if self._has_valid_citation(generated, safe_hits):
                    answer = generated
                    mode = "llm"
                else:
                    flags.append("ungrounded_llm_fallback")
            except Exception:
                flags.append("llm_error_fallback")
        return self._result(answer, citations, confidence, False, mode, flags, request_id, started)

    @staticmethod
    def _extractive_answer(hits: list[SearchHit]) -> str:
        best = hits[0].chunk
        sentence = re.split(r"(?<=[.!?])\s+", best.text.strip())[0]
        return f"{sentence} [{best.id}]"

    @staticmethod
    def _has_valid_citation(answer: str, hits: list[SearchHit]) -> bool:
        return any(f"[{hit.chunk.id}]" in answer for hit in hits)

    @staticmethod
    def _result(answer, citations, confidence, abstained, mode, flags, request_id, started):
        return QueryResult(
            answer=answer,
            citations=citations,
            confidence=confidence,
            abstained=abstained,
            mode=mode,
            safety_flags=list(dict.fromkeys(flags)),
            request_id=request_id,
            latency_ms=(time.perf_counter() - started) * 1000,
        )

