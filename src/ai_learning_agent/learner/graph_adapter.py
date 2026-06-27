"""Adapter between the learner overlay and the existing KG brick."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from ai_learning_agent.kg.models import KnowledgeGraph, KnowledgeNode

TRACKABLE_KINDS = {"concept", "formula", "problem_type"}


def is_trackable_node(node: KnowledgeNode, trackable_kinds: Iterable[str] = TRACKABLE_KINDS) -> bool:
    return node.kind in set(trackable_kinds)


def node_mastery_threshold(node: KnowledgeNode) -> float:
    value = node.properties.get("mastery_threshold")
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    if node.properties.get("is_threshold_concept") or node.properties.get("threshold_concept"):
        return 0.90
    if node.kind == "formula":
        return 0.75
    return 0.80


def node_difficulty(node: KnowledgeNode) -> float:
    value = node.properties.get("difficulty")
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    if node.kind == "formula":
        return 0.45
    if node.kind == "problem_type":
        return 0.65
    bloom = str(node.properties.get("bloom_level", "")).lower()
    if bloom in {"remember", "understand"}:
        return 0.35
    if bloom in {"apply"}:
        return 0.55
    if bloom in {"analyze", "evaluate", "create"}:
        return 0.75
    return 0.50


class KnowledgeGraphLearningAdapter:
    """Read learning-relevant structure from a KnowledgeGraph."""

    def __init__(self, graph: KnowledgeGraph, trackable_kinds: Iterable[str] = TRACKABLE_KINDS) -> None:
        self.graph = graph
        self.trackable_kinds = set(trackable_kinds)
        self._prereqs: dict[str, list[str]] = defaultdict(list)
        self._dependents: dict[str, list[str]] = defaultdict(list)
        for edge in graph.edges:
            if edge.relation_type != "REQUIRES":
                continue
            # Builder convention: concept/problem source REQUIRES prerequisite target.
            self._prereqs[edge.source_id].append(edge.target_id)
            self._dependents[edge.target_id].append(edge.source_id)

    def trackable_nodes(self) -> list[KnowledgeNode]:
        nodes = [n for n in self.graph.nodes.values() if is_trackable_node(n, self.trackable_kinds)]
        return sorted(nodes, key=lambda n: (node_difficulty(n), n.label))

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self.graph.nodes.get(node_id)

    def prerequisites_of(self, node_id: str) -> list[KnowledgeNode]:
        return [self.graph.nodes[nid] for nid in self._prereqs.get(node_id, []) if nid in self.graph.nodes]

    def dependents_of(self, node_id: str) -> list[KnowledgeNode]:
        return [self.graph.nodes[nid] for nid in self._dependents.get(node_id, []) if nid in self.graph.nodes]

    def transitive_prerequisites_of(self, node_id: str) -> list[KnowledgeNode]:
        seen: set[str] = set()
        result: list[KnowledgeNode] = []

        def visit(current: str) -> None:
            for prereq in self.prerequisites_of(current):
                if prereq.id in seen:
                    continue
                seen.add(prereq.id)
                visit(prereq.id)
                result.append(prereq)

        visit(node_id)
        return result
