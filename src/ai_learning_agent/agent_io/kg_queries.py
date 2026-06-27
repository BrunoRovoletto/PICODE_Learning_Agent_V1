"""Agent-facing KG query helpers.

These functions are the first stable tool boundary for Pi. They intentionally
wrap the canonical KG instead of changing it. The graph remains the teacher KG;
learner state is attached as an optional overlay at packet-construction time.
"""

from __future__ import annotations

from dataclasses import asdict
from difflib import SequenceMatcher
from typing import Any, Iterable
import re

from ai_learning_agent.kg.models import KnowledgeEdge, KnowledgeGraph, KnowledgeNode, SourceRef
from ai_learning_agent.learner.graph_adapter import node_difficulty, node_mastery_threshold
from ai_learning_agent.learner.models import LearnerProfile, mastery_status

DEFAULT_NODE_PROPERTIES: dict[str, Any] = {
    "extended_description": "",
    "difficulty": None,
    "mastery_threshold": None,
    "estimated_minutes": 15,
    "exam_relevance": 0.5,
    "topic": None,
    "is_threshold_concept": False,
    "common_traps": [],
    "exercise_ladder_level": None,
}


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^\w\s=+\-*/^().,]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def source_ref_to_dict(source: SourceRef) -> dict[str, Any]:
    return asdict(source)


def standardized_properties(node: KnowledgeNode) -> dict[str, Any]:
    """Return node properties with default metadata fields standardized.

    We keep these as properties rather than changing the core KG dataclass.
    """
    props = {**DEFAULT_NODE_PROPERTIES, **dict(node.properties or {})}
    props["difficulty"] = node_difficulty(node)
    props["mastery_threshold"] = node_mastery_threshold(node)
    props["estimated_minutes"] = int(props.get("estimated_minutes") or 15)
    props["exam_relevance"] = float(props.get("exam_relevance") or 0.5)
    props["common_traps"] = list(props.get("common_traps") or [])
    props["is_threshold_concept"] = bool(props.get("is_threshold_concept") or props.get("threshold_concept"))
    return props


def learner_state_to_dict(node: KnowledgeNode, profile: LearnerProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    threshold = node_mastery_threshold(node)
    state = profile.get_state(node.id)
    return {
        "node_id": node.id,
        "mastery": state.mastery,
        "confidence": state.confidence,
        "attempts": state.attempts,
        "correct_attempts": state.correct_attempts,
        "streak": state.streak,
        "status": mastery_status(state.mastery, threshold),
        "gap_type": state.gap_type,
        "common_mistakes": list(state.common_mistakes),
        "last_attempt_at": state.last_attempt_at,
        "next_review_at": state.next_review_at,
        "threshold": threshold,
    }


def compact_edge(edge: KnowledgeEdge) -> dict[str, Any]:
    return {
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "relation_type": edge.relation_type,
        "weight": edge.weight,
        "evidence": edge.evidence,
    }


def node_to_packet(
    node: KnowledgeNode,
    *,
    profile: LearnerProfile | None = None,
    include_sources: bool = True,
    fields: Iterable[str] | None = None,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "id": node.id,
        "label": node.label,
        "kind": node.kind,
        "description": node.description,
        "extended_description": standardized_properties(node).get("extended_description", ""),
        "aliases": list(node.aliases),
        "properties": standardized_properties(node),
    }
    if include_sources:
        packet["sources"] = [source_ref_to_dict(source) for source in node.sources]
    learner = learner_state_to_dict(node, profile)
    if learner is not None:
        packet["learner_state"] = learner

    if fields is None:
        return packet

    requested = list(fields)
    selected = {field: packet[field] for field in requested if field in packet}
    # Preserve identity so partial packets remain usable by Pi.
    selected.setdefault("id", node.id)
    selected.setdefault("label", node.label)
    selected.setdefault("kind", node.kind)
    return selected


def _node_search_haystacks(node: KnowledgeNode) -> dict[str, str]:
    props = standardized_properties(node)
    source_quotes = " ".join(src.quote or "" for src in node.sources)
    source_titles = " ".join(src.title or "" for src in node.sources)
    aliases = " ".join(node.aliases)
    properties_text = " ".join(str(v) for v in props.values() if isinstance(v, str | int | float | bool))
    return {
        "id": normalize_text(node.id),
        "label": normalize_text(node.label),
        "aliases": normalize_text(aliases),
        "description": normalize_text(node.description),
        "extended_description": normalize_text(props.get("extended_description", "")),
        "properties": normalize_text(properties_text),
        "sources": normalize_text(f"{source_quotes} {source_titles}"),
    }


def _score_haystack(query: str, haystack: str) -> float:
    if not query or not haystack:
        return 0.0
    if query == haystack:
        return 1.0
    if query in haystack:
        return 0.78
    query_tokens = set(query.split())
    hay_tokens = set(haystack.split())
    overlap = len(query_tokens & hay_tokens) / max(1, len(query_tokens))
    fuzzy = SequenceMatcher(None, query, haystack[: max(40, len(query) * 4)]).ratio()
    return max(overlap * 0.72, fuzzy * 0.55)


def score_node(node: KnowledgeNode, query: str) -> tuple[float, list[str]]:
    q = normalize_text(query)
    if not q:
        return 0.0, []
    haystacks = _node_search_haystacks(node)
    field_weights = {
        "id": 1.25,
        "label": 1.18,
        "aliases": 1.12,
        "description": 1.0,
        "extended_description": 0.95,
        "properties": 0.82,
        "sources": 0.72,
    }
    scored: list[tuple[str, float]] = [
        (field, min(1.0, _score_haystack(q, text) * field_weights.get(field, 1.0)))
        for field, text in haystacks.items()
    ]
    # Strong exact id/label/alias boosts.
    if q == haystacks["id"]:
        scored.append(("id", 1.0))
    if q == haystacks["label"]:
        scored.append(("label", 0.98))
    if any(q == normalize_text(alias) for alias in node.aliases):
        scored.append(("aliases", 0.96))
    best = max(score for _, score in scored) if scored else 0.0
    matched = [field for field, score in scored if score >= max(0.25, best - 0.08)]
    return best, sorted(set(matched))


def search_nodes(
    graph: KnowledgeGraph,
    query: str,
    *,
    limit: int = 8,
    kinds: Iterable[str] | None = None,
    min_score: float = 0.18,
) -> list[dict[str, Any]]:
    kind_set = set(kinds) if kinds is not None else None
    results: list[dict[str, Any]] = []
    for node in graph.nodes.values():
        if kind_set is not None and node.kind not in kind_set:
            continue
        score, matched_fields = score_node(node, query)
        if score < min_score:
            continue
        results.append({"node_id": node.id, "score": round(score, 4), "matched_fields": matched_fields})
    results.sort(key=lambda item: (-item["score"], graph.nodes[item["node_id"]].label))
    return results[:limit]


def resolve_node(graph: KnowledgeGraph, query_or_id: str) -> KnowledgeNode | None:
    if query_or_id in graph.nodes:
        return graph.nodes[query_or_id]
    normalized = normalize_text(query_or_id)
    for node in graph.nodes.values():
        if normalize_text(node.label) == normalized:
            return node
        if any(normalize_text(alias) == normalized for alias in node.aliases):
            return node
    matches = search_nodes(graph, query_or_id, limit=1)
    return graph.nodes[matches[0]["node_id"]] if matches else None


def get_node(
    graph: KnowledgeGraph,
    query_or_id: str,
    *,
    profile: LearnerProfile | None = None,
    fields: Iterable[str] | None = None,
    include_relatives: bool = False,
    include_sources: bool = True,
    include_user_state: bool = True,
) -> dict[str, Any]:
    node = resolve_node(graph, query_or_id)
    if node is None:
        return {"query": query_or_id, "found": False, "matches": search_nodes(graph, query_or_id, limit=5)}
    profile_for_packet = profile if include_user_state else None
    packet = node_to_packet(node, profile=profile_for_packet, include_sources=include_sources, fields=fields)
    result: dict[str, Any] = {"query": query_or_id, "found": True, "node": packet}
    if include_relatives:
        result["relatives"] = get_node_relatives(
            graph,
            node.id,
            profile=profile_for_packet,
            depth=1,
            direction="both",
            unpack=False,
        )["relatives"]
    return result


def _edge_neighbors(graph: KnowledgeGraph, node_id: str, direction: str, relation_types: set[str] | None) -> list[tuple[str, KnowledgeEdge, str]]:
    neighbors: list[tuple[str, KnowledgeEdge, str]] = []
    for edge in graph.edges:
        if relation_types is not None and edge.relation_type not in relation_types:
            continue
        if edge.relation_type == "REQUIRES":
            if direction in {"parents", "both"} and edge.source_id == node_id:
                neighbors.append((edge.target_id, edge, "parent"))
            if direction in {"children", "both"} and edge.target_id == node_id:
                neighbors.append((edge.source_id, edge, "child"))
            continue
        if direction in {"children", "both"} and edge.source_id == node_id:
            neighbors.append((edge.target_id, edge, "out"))
        if direction in {"parents", "both"} and edge.target_id == node_id:
            neighbors.append((edge.source_id, edge, "in"))
    return neighbors


def get_node_relatives(
    graph: KnowledgeGraph,
    node: str,
    *,
    profile: LearnerProfile | None = None,
    depth: int = 1,
    direction: str = "both",
    relation_types: Iterable[str] | None = None,
    unpack: bool = False,
) -> dict[str, Any]:
    resolved = resolve_node(graph, node)
    if resolved is None:
        return {"query": node, "found": False, "relatives": []}
    if direction not in {"parents", "children", "both"}:
        raise ValueError("direction must be 'parents', 'children', or 'both'")
    relation_set = set(relation_types) if relation_types is not None else None
    max_depth = max(0, int(depth))
    seen = {resolved.id}
    frontier = [(resolved.id, 0)]
    relatives: list[dict[str, Any]] = []
    while frontier:
        current_id, current_depth = frontier.pop(0)
        if current_depth >= max_depth:
            continue
        for neighbor_id, edge, edge_direction in _edge_neighbors(graph, current_id, direction, relation_set):
            if neighbor_id not in graph.nodes:
                continue
            next_depth = current_depth + 1
            neighbor = graph.nodes[neighbor_id]
            item: dict[str, Any] = {
                "node_id": neighbor.id,
                "label": neighbor.label,
                "kind": neighbor.kind,
                "depth": next_depth,
                "direction": edge_direction,
                "via_relation": edge.relation_type,
                "edge": compact_edge(edge),
            }
            if unpack:
                item["node"] = node_to_packet(neighbor, profile=profile, include_sources=False)
            relatives.append(item)
            if neighbor_id not in seen:
                seen.add(neighbor_id)
                frontier.append((neighbor_id, next_depth))
    relatives.sort(key=lambda item: (item["depth"], item["direction"], item["label"]))
    return {
        "query": node,
        "found": True,
        "resolved_node": node_to_packet(resolved, profile=profile, include_sources=False),
        "depth": max_depth,
        "direction": direction,
        "relation_types": sorted(relation_set) if relation_set else None,
        "relatives": relatives,
    }


def _direct_prereq_ids(graph: KnowledgeGraph, node_id: str) -> list[str]:
    ids = [edge.target_id for edge in graph.edges if edge.relation_type == "REQUIRES" and edge.source_id == node_id]
    return [node_id for node_id in ids if node_id in graph.nodes]


def _path_minutes(graph: KnowledgeGraph, path: list[str]) -> int:
    total = 0
    for node_id in path:
        total += int(standardized_properties(graph.nodes[node_id]).get("estimated_minutes") or 15)
    return total


def get_from_first_principles(
    graph: KnowledgeGraph,
    node: str,
    *,
    profile: LearnerProfile | None = None,
    max_paths: int = 3,
    pruned: bool = True,
) -> dict[str, Any]:
    target = resolve_node(graph, node)
    if target is None:
        return {"query": node, "found": False, "paths": []}

    def build_paths(node_id: str, stack: set[str]) -> list[list[str]]:
        if node_id in stack:
            return [[node_id]]
        prereqs = _direct_prereq_ids(graph, node_id)
        if not prereqs:
            return [[node_id]]
        paths: list[list[str]] = []
        for prereq_id in sorted(prereqs, key=lambda nid: graph.nodes[nid].label):
            for subpath in build_paths(prereq_id, stack | {node_id}):
                paths.append(subpath + [node_id])
        return paths

    paths = build_paths(target.id, set())
    paths.sort(key=lambda path: (len(path), _path_minutes(graph, path), [graph.nodes[nid].label for nid in path]))
    if pruned:
        paths = paths[: max(1, int(max_paths))]
    return {
        "query": node,
        "found": True,
        "target": node_to_packet(target, profile=profile, include_sources=False),
        "pruned": pruned,
        "paths": [
            {
                "node_ids": path,
                "aliases": [graph.nodes[nid].aliases for nid in path],
                "labels": [graph.nodes[nid].label for nid in path],
                "total_estimated_minutes": _path_minutes(graph, path),
                "nodes": [node_to_packet(graph.nodes[nid], profile=profile, include_sources=False) for nid in path],
            }
            for path in paths[: max(1, int(max_paths))]
        ],
    }
