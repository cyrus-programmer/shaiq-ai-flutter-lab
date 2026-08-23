from __future__ import annotations

import re
from pathlib import Path

from .models import Chunk
from .safety import has_prompt_injection


def _slug(path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def chunk_markdown(path: Path, max_chars: int = 900, overlap_chars: int = 120) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8").strip()
    title_match = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem.replace("-", " ").title()
    body = re.sub(r"^#\s+.+$", "", raw, count=1, flags=re.MULTILINE).strip()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    texts: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > max_chars:
            texts.append(current)
            overlap = current[-overlap_chars:].lstrip() if overlap_chars else ""
            current = f"{overlap}\n\n{paragraph}".strip()
        else:
            current = candidate
    if current:
        texts.append(current)
    slug = _slug(path)
    return [
        Chunk(
            id=f"{slug}:{index}",
            source=path.name,
            title=title,
            text=text,
            position=index,
            unsafe=has_prompt_injection(text),
        )
        for index, text in enumerate(texts)
    ]


def load_knowledge(directory: Path) -> list[Chunk]:
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Knowledge directory not found: {directory}")
    chunks: list[Chunk] = []
    for path in sorted(directory.glob("*.md")):
        chunks.extend(chunk_markdown(path))
    if not chunks:
        raise ValueError(f"No Markdown knowledge files found in {directory}")
    return chunks

