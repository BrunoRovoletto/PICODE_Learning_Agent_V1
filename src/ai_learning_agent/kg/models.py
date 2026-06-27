"""Core data models for the knowledge-graph brick.

The KG brick intentionally uses plain dataclasses and JSON-serializable
structures. This keeps the brick self-contained and easy to connect to Pi,
LLM extractors, Neo4j, SQLite, or a future web app without coupling it to any
one framework.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

NodeKind = Literal["concept", "formula", "problem_type", "source_chunk"]
RelationType = Literal[
    "REQUIRES",
    "RELATED_TO",
    "HAS_FORMULA",
    "USED_IN_PROBLEM_TYPE",
    "MENTIONED_IN",
]


@dataclass(frozen=True)
class SourceDocument:
    """A source text document, usually one extracted book/PDF section."""

    doc_id: str
    title: str
    text: str
    source_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceChunk:
    """A stable chunk of text used as KG extraction input."""

    chunk_id: str
    doc_id: str
    title: str
    text: str
    ordinal: int
    source_path: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceRef:
    """Provenance reference from a graph element back to course material."""

    doc_id: str
    chunk_id: str
    title: str
    source_path: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    quote: str | None = None


@dataclass
class ExtractedConcept:
    """LLM/deterministic extraction output for one concept in one chunk.

    This is inspired by OpenTutor LOOM extraction but extended for Physics 1:
    formulas and problem types are first-class extraction fields.
    """

    name: str
    description: str = ""
    prerequisites: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    formulas: list[str] = field(default_factory=list)
    problem_types: list[str] = field(default_factory=list)
    bloom_level: str = "understand"
    confidence: float = 0.7
    evidence: str | None = None
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_mapping(data: dict[str, Any]) -> "ExtractedConcept":
        return ExtractedConcept(
            name=str(data.get("name", "")).strip(),
            description=str(data.get("description", "")).strip(),
            prerequisites=[str(x).strip() for x in data.get("prerequisites", []) if str(x).strip()],
            related=[str(x).strip() for x in data.get("related", []) if str(x).strip()],
            formulas=[str(x).strip() for x in data.get("formulas", []) if str(x).strip()],
            problem_types=[str(x).strip() for x in data.get("problem_types", []) if str(x).strip()],
            bloom_level=str(data.get("bloom_level", "understand")).strip() or "understand",
            confidence=float(data.get("confidence", 0.7) or 0.7),
            evidence=(str(data["evidence"]).strip() if data.get("evidence") else None),
            aliases=[str(x).strip() for x in data.get("aliases", []) if str(x).strip()],
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class KnowledgeNode:
    """Canonical node in the course knowledge graph."""

    id: str
    label: str
    kind: NodeKind
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    sources: list[SourceRef] = field(default_factory=list)


@dataclass
class KnowledgeEdge:
    """Directed typed relationship between two graph nodes."""

    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    evidence: str | None = None
    sources: list[SourceRef] = field(default_factory=list)


@dataclass
class KnowledgeGraph:
    """Serializable knowledge graph.

    `nodes` is keyed by stable node id. Edges are intentionally kept as a list
    because duplicate evidence can be merged at build time by the builder.
    """

    nodes: dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: list[KnowledgeEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "schema": "ai_learning_agent.kg.v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                **self.metadata,
            },
            "nodes": [asdict(node) for node in sorted(self.nodes.values(), key=lambda n: (n.kind, n.label))],
            "edges": [asdict(edge) for edge in self.edges],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "KnowledgeGraph":
        graph = KnowledgeGraph(metadata=dict(data.get("metadata", {}) or {}))
        for item in data.get("nodes", []):
            sources = [SourceRef(**src) for src in item.get("sources", [])]
            node = KnowledgeNode(
                id=item["id"],
                label=item["label"],
                kind=item["kind"],
                description=item.get("description", ""),
                aliases=list(item.get("aliases", [])),
                properties=dict(item.get("properties", {}) or {}),
                sources=sources,
            )
            graph.nodes[node.id] = node
        for item in data.get("edges", []):
            graph.edges.append(
                KnowledgeEdge(
                    source_id=item["source_id"],
                    target_id=item["target_id"],
                    relation_type=item["relation_type"],
                    weight=float(item.get("weight", 1.0)),
                    evidence=item.get("evidence"),
                    sources=[SourceRef(**src) for src in item.get("sources", [])],
                )
            )
        return graph
