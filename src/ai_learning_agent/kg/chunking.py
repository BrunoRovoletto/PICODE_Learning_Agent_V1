"""Text chunking utilities for book-scale KG extraction."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from .models import SourceChunk, SourceDocument


def _stable_chunk_id(doc_id: str, ordinal: int, text: str) -> str:
    digest = hashlib.sha1(f"{doc_id}:{ordinal}:{text[:200]}".encode("utf-8")).hexdigest()[:12]
    return f"chunk:{doc_id}:{ordinal:05d}:{digest}"


class TextChunker:
    """Paragraph-aware character chunker.

    PDF extraction is intentionally not inside this brick. This brick accepts
    text and turns it into stable extraction chunks.
    """

    def __init__(self, max_chars: int = 3500, overlap_chars: int = 300) -> None:
        if max_chars < 500:
            raise ValueError("max_chars should be at least 500")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be >= 0 and < max_chars")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk_document(self, document: SourceDocument) -> list[SourceChunk]:
        paragraphs = [p.strip() for p in document.text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs or [document.text.strip()]:
            if not paragraph:
                continue
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= self.max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = paragraph
            while len(current) > self.max_chars:
                chunks.append(current[: self.max_chars])
                current = current[self.max_chars - self.overlap_chars :]
        if current:
            chunks.append(current)

        result: list[SourceChunk] = []
        for ordinal, text in enumerate(chunks):
            result.append(
                SourceChunk(
                    chunk_id=_stable_chunk_id(document.doc_id, ordinal, text),
                    doc_id=document.doc_id,
                    title=document.title,
                    text=text,
                    ordinal=ordinal,
                    source_path=document.source_path,
                    metadata=dict(document.metadata),
                )
            )
        return result

    def rechunk_with_title(self, chunks: list[SourceChunk], title_suffix: str) -> list[SourceChunk]:
        """Utility for later page/section processors that need retitling."""
        return [replace(chunk, title=f"{chunk.title} — {title_suffix}") for chunk in chunks]
