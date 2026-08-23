from __future__ import annotations

import math
import re
from collections import Counter

from .models import Chunk, SearchHit

TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.I)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text) if len(token) > 1]


class BM25Retriever:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        if not chunks:
            raise ValueError("At least one chunk is required")
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self._tokens = [tokenize(f"{chunk.title} {chunk.text}") for chunk in chunks]
        self._counts = [Counter(tokens) for tokens in self._tokens]
        self._avg_len = sum(map(len, self._tokens)) / len(self._tokens)
        doc_freq: Counter[str] = Counter()
        for tokens in self._tokens:
            doc_freq.update(set(tokens))
        count = len(chunks)
        self._idf = {
            term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in doc_freq.items()
        }

    def search(self, query: str, top_k: int = 4) -> list[SearchHit]:
        query_terms = tokenize(query)
        if not query_terms:
            return []
        scored: list[SearchHit] = []
        for chunk, terms, counts in zip(self.chunks, self._tokens, self._counts):
            score = 0.0
            length_norm = 1 - self.b + self.b * len(terms) / max(self._avg_len, 1)
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                numerator = frequency * (self.k1 + 1)
                denominator = frequency + self.k1 * length_norm
                score += self._idf.get(term, 0.0) * numerator / denominator
            if score > 0:
                normalized = score / (score + max(len(set(query_terms)), 1))
                scored.append(SearchHit(chunk=chunk, score=normalized))
        return sorted(scored, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]

