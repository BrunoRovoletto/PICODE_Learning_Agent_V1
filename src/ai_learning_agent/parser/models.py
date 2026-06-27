"""Data models for the parser brick.

This brick is intentionally independent from PDF libraries and KG building.
It outputs ordered, source-grounded text/formula chunks that the KG brick can
consume as `SourceChunk` JSONL.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ChunkKind = Literal["section", "formula_context", "paragraph"]
FormulaKind = Literal["display_math", "inline_math", "equation_env", "formula_line"]


@dataclass(frozen=True)
class ParsedFormula:
    """A formula/equation detected in parsed text."""

    formula_id: str
    text: str
    kind: FormulaKind
    start_char: int
    end_char: int
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedSection:
    """Markdown-derived content section."""

    section_id: str
    title: str
    level: int
    text: str
    start_char: int
    end_char: int
    parent_id: str | None = None
    ordinal: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParserChunk:
    """Final parser output chunk.

    A chunk can be centered on a formula or just a section/paragraph chunk.
    It carries previous/next ids for later adaptiveKG-style sequential linking.
    """

    chunk_id: str
    doc_id: str
    title: str
    text: str
    ordinal: int
    kind: ChunkKind
    source_path: str | None = None
    section_id: str | None = None
    formula_ids: list[str] = field(default_factory=list)
    previous_chunk_id: str | None = None
    next_chunk_id: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_kg_source_chunk_dict(self) -> dict[str, Any]:
        """Return shape compatible with ai_learning_agent.kg.models.SourceChunk."""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "ordinal": self.ordinal,
            "source_path": self.source_path,
            "page_start": None,
            "page_end": None,
            "metadata": {
                "parser_kind": self.kind,
                "section_id": self.section_id,
                "formula_ids": self.formula_ids,
                "previous_chunk_id": self.previous_chunk_id,
                "next_chunk_id": self.next_chunk_id,
                "start_char": self.start_char,
                "end_char": self.end_char,
                **self.metadata,
            },
        }


@dataclass(frozen=True)
class ParsedDocument:
    """Complete parser output for one book/document."""

    doc_id: str
    title: str
    markdown: str
    source_path: str | None = None
    sections: list[ParsedSection] = field(default_factory=list)
    formulas: list[ParsedFormula] = field(default_factory=list)
    chunks: list[ParserChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
