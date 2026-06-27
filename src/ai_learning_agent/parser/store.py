"""Parser brick IO helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .models import ParsedDocument, ParserChunk


def write_parsed_document(document: ParsedDocument, path: str | Path) -> None:
    Path(path).write_text(json.dumps(document.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def write_parser_chunks_jsonl(chunks: Iterable[ParserChunk], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")


def write_kg_chunks_jsonl(chunks: Iterable[ParserChunk], path: str | Path) -> None:
    """Write chunks in KG SourceChunk-compatible JSONL shape."""
    with Path(path).open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.to_kg_source_chunk_dict(), ensure_ascii=False) + "\n")
