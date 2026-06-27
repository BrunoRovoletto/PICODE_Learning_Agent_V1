"""Knowledge graph builder brick.

Chosen mechanism: OpenTutor-style LOOM/Graphusion.

Reimplemented here as a clean, self-contained pipeline:
1. receive source chunks;
2. receive extracted concepts per chunk;
3. fuse duplicate concepts across chunks/books;
4. create typed nodes and relationships;
5. preserve provenance to original sources.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .dedupe import LexicalNodeDeduper, NodeDeduper, stable_node_id
from .models import (
    ExtractedConcept,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeKind,
    SourceChunk,
    SourceRef,
)


@dataclass
class BuildStats:
    chunks_seen: int = 0
    concepts_seen: int = 0
    nodes_created: int = 0
    edges_created: int = 0
    duplicate_nodes_merged: int = 0


class KnowledgeGraphBuilder:
    """Build and fuse a Physics knowledge graph from extracted chunks."""

    def __init__(self, deduper: NodeDeduper | None = None) -> None:
        self.graph = KnowledgeGraph(metadata={"builder": "KnowledgeGraphBuilder", "mechanism": "loom_graphusion_reimplementation"})
        self.deduper = deduper or LexicalNodeDeduper()
        self.stats = BuildStats()
        self._labels_by_kind: dict[NodeKind, list[str]] = defaultdict(list)
        self._id_by_kind_label: dict[tuple[NodeKind, str], str] = {}
        self._edge_index: dict[tuple[str, str, str], int] = {}

    def add_chunk_extraction(self, chunk: SourceChunk, concepts: list[ExtractedConcept]) -> None:
        """Add all extracted concepts for a chunk."""
        self.stats.chunks_seen += 1
        source_ref = SourceRef(
            doc_id=chunk.doc_id,
            chunk_id=chunk.chunk_id,
            title=chunk.title,
            source_path=chunk.source_path,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
        )
        chunk_node_id = self._upsert_node(
            label=chunk.title or chunk.chunk_id,
            kind="source_chunk",
            description=chunk.text[:500],
            source=source_ref,
            properties={"doc_id": chunk.doc_id, "chunk_id": chunk.chunk_id, "ordinal": chunk.ordinal},
        )

        for concept in concepts:
            if not concept.name:
                continue
            self.stats.concepts_seen += 1
            concept_ref = SourceRef(
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                source_path=chunk.source_path,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                quote=concept.evidence,
            )
            concept_id = self._upsert_node(
                label=concept.name,
                kind="concept",
                description=concept.description,
                aliases=concept.aliases,
                source=concept_ref,
                properties={"bloom_level": concept.bloom_level, "confidence": concept.confidence, **concept.metadata},
            )
            self._upsert_edge(concept_id, chunk_node_id, "MENTIONED_IN", source=concept_ref, evidence=concept.evidence, weight=concept.confidence)

            for prereq in concept.prerequisites:
                prereq_id = self._upsert_node(label=prereq, kind="concept", source=concept_ref)
                self._upsert_edge(concept_id, prereq_id, "REQUIRES", source=concept_ref, evidence=concept.evidence, weight=concept.confidence)

            for related in concept.related:
                related_id = self._upsert_node(label=related, kind="concept", source=concept_ref)
                self._upsert_edge(concept_id, related_id, "RELATED_TO", source=concept_ref, evidence=concept.evidence, weight=concept.confidence)

            for formula in concept.formulas:
                formula_id = self._upsert_node(label=formula, kind="formula", source=concept_ref)
                self._upsert_edge(concept_id, formula_id, "HAS_FORMULA", source=concept_ref, evidence=concept.evidence, weight=concept.confidence)

            for problem_type in concept.problem_types:
                problem_type_id = self._upsert_node(label=problem_type, kind="problem_type", source=concept_ref)
                self._upsert_edge(concept_id, problem_type_id, "USED_IN_PROBLEM_TYPE", source=concept_ref, evidence=concept.evidence, weight=concept.confidence)

    def build(self) -> KnowledgeGraph:
        """Return the graph with build stats in metadata."""
        self.graph.metadata["stats"] = self.stats.__dict__.copy()
        self.graph.metadata["node_count"] = len(self.graph.nodes)
        self.graph.metadata["edge_count"] = len(self.graph.edges)
        return self.graph

    def _upsert_node(
        self,
        label: str,
        kind: NodeKind,
        description: str = "",
        aliases: list[str] | None = None,
        source: SourceRef | None = None,
        properties: dict | None = None,
    ) -> str:
        label = label.strip()
        if not label:
            raise ValueError("node label cannot be empty")

        aliases = aliases or []
        direct_id = self._id_by_kind_label.get((kind, label))
        if direct_id:
            node_id = direct_id
            canonical_label = self.graph.nodes[node_id].label
        else:
            match_label = self.deduper.find_match(label, self._labels_by_kind[kind])
            canonical_label = match_label or label
            if match_label:
                self.stats.duplicate_nodes_merged += 1
            node_id = self._id_by_kind_label.get((kind, canonical_label))

        if node_id is None:
            node_id = stable_node_id(kind, canonical_label)
            self.graph.nodes[node_id] = KnowledgeNode(
                id=node_id,
                label=canonical_label,
                kind=kind,
                description=description,
                aliases=[],
                properties=dict(properties or {}),
                sources=[],
            )
            self._register_label(kind, canonical_label, node_id)
            self.stats.nodes_created += 1

        node = self.graph.nodes[node_id]
        if description and len(description) > len(node.description):
            node.description = description
        for alias in [label, *aliases]:
            if alias != node.label and alias not in node.aliases:
                node.aliases.append(alias)
            self._register_label(kind, alias, node_id)
        if properties:
            node.properties.update({k: v for k, v in properties.items() if v not in (None, "", [])})
        if source and source not in node.sources:
            node.sources.append(source)
        return node_id

    def _register_label(self, kind: NodeKind, label: str, node_id: str) -> None:
        label = label.strip()
        if not label:
            return
        if (kind, label) not in self._id_by_kind_label:
            self._id_by_kind_label[(kind, label)] = node_id
        if label not in self._labels_by_kind[kind]:
            self._labels_by_kind[kind].append(label)

    def _upsert_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        source: SourceRef | None = None,
        evidence: str | None = None,
        weight: float = 1.0,
    ) -> None:
        key = (source_id, target_id, relation_type)
        if key in self._edge_index:
            edge = self.graph.edges[self._edge_index[key]]
            edge.weight = max(edge.weight, weight)
            if evidence and not edge.evidence:
                edge.evidence = evidence
            if source and source not in edge.sources:
                edge.sources.append(source)
            return
        edge = KnowledgeEdge(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,  # type: ignore[arg-type]
            weight=weight,
            evidence=evidence,
            sources=[source] if source else [],
        )
        self._edge_index[key] = len(self.graph.edges)
        self.graph.edges.append(edge)
        self.stats.edges_created += 1
