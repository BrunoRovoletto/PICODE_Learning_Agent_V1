"""JSON/JSONL IO helpers for KG brick inputs and outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import ExtractedConcept, KnowledgeGraph, SourceChunk, SourceDocument


def read_documents_jsonl(path: str | Path) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            docs.append(SourceDocument(**item))
    return docs


def write_chunks_jsonl(chunks: Iterable[SourceChunk], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.__dict__, ensure_ascii=False) + "\n")


def read_chunks_jsonl(path: str | Path) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            chunks.append(SourceChunk(**json.loads(line)))
    return chunks


def read_extractions_jsonl(path: str | Path) -> dict[str, list[ExtractedConcept]]:
    """Read extractions keyed by chunk_id.

    Accepted line shape:
    {"chunk_id": "...", "concepts": [{...}]}
    """
    by_chunk: dict[str, list[ExtractedConcept]] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            concepts = [ExtractedConcept.from_mapping(c) for c in item.get("concepts", [])]
            by_chunk[item["chunk_id"]] = [c for c in concepts if c.name]
    return by_chunk


def write_extractions_jsonl(extractions: dict[str, list[ExtractedConcept]], path: str | Path) -> None:
    """Write extractions keyed by chunk_id."""
    from dataclasses import asdict

    with Path(path).open("w", encoding="utf-8") as handle:
        for chunk_id, concepts in extractions.items():
            handle.write(
                json.dumps(
                    {"chunk_id": chunk_id, "concepts": [asdict(concept) for concept in concepts]},
                    ensure_ascii=False,
                )
                + "\n"
            )


def write_graph_json(graph: KnowledgeGraph, path: str | Path) -> None:
    Path(path).write_text(json.dumps(graph.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def read_graph_json(path: str | Path) -> KnowledgeGraph:
    return KnowledgeGraph.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
