"""Compact context retrieval for Pi.

This is the intent-level retrieval API. It starts dependency-free with
lexical/fuzzy KG search and graph expansion; a vector backend can be added later
behind the same function.
"""

from __future__ import annotations

from typing import Any

from ai_learning_agent.kg.models import KnowledgeGraph
from ai_learning_agent.learner.models import LearnerProfile

from .kg_queries import get_node_relatives, node_to_packet, search_nodes


def _unique_append(items: list[dict[str, Any]], item: dict[str, Any], key: str = "id") -> None:
    value = item.get(key) or item.get("node_id")
    if value is None:
        items.append(item)
        return
    if all((existing.get(key) or existing.get("node_id")) != value for existing in items):
        items.append(item)


def _source_quotes(nodes: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    quotes: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for node in nodes:
        node_packet = node.get("node", node)
        for source in node_packet.get("sources", []) or []:
            quote = source.get("quote")
            if not quote:
                continue
            key = (source.get("doc_id", ""), source.get("chunk_id", ""), quote)
            if key in seen:
                continue
            seen.add(key)
            quotes.append(
                {
                    "node_id": node_packet.get("id"),
                    "node_label": node_packet.get("label"),
                    "doc_id": source.get("doc_id"),
                    "chunk_id": source.get("chunk_id"),
                    "title": source.get("title"),
                    "source_path": source.get("source_path"),
                    "quote": quote,
                }
            )
            if len(quotes) >= limit:
                return quotes
    return quotes


def context_retrieve(
    graph: KnowledgeGraph,
    query: str,
    *,
    profile: LearnerProfile | None = None,
    intent: str = "teach",
    limit: int = 8,
    include_user_state: bool = True,
    neighbor_depth: int = 1,
) -> dict[str, Any]:
    matches = search_nodes(graph, query, limit=limit)
    profile_for_packet = profile if include_user_state else None

    matched_nodes: list[dict[str, Any]] = []
    supporting_nodes: list[dict[str, Any]] = []
    formulas: list[dict[str, Any]] = []
    prerequisites: list[dict[str, Any]] = []
    problem_types: list[dict[str, Any]] = []
    related: list[dict[str, Any]] = []

    for match in matches:
        node = graph.nodes[match["node_id"]]
        packet = node_to_packet(node, profile=profile_for_packet, include_sources=True)
        matched_nodes.append({**match, "node": packet})

        relatives = get_node_relatives(
            graph,
            node.id,
            profile=profile_for_packet,
            depth=neighbor_depth,
            direction="both",
            unpack=True,
        )["relatives"]
        for rel in relatives:
            rel_node = rel.get("node", {})
            rel_item = {
                "role": rel["direction"],
                "via_relation": rel["via_relation"],
                "depth": rel["depth"],
                "node": rel_node,
            }
            _unique_append(supporting_nodes, {"node_id": rel["node_id"], **rel_item}, key="node_id")
            if rel["via_relation"] == "REQUIRES" and rel["direction"] == "parent":
                _unique_append(prerequisites, {"node_id": rel["node_id"], **rel_item}, key="node_id")
            elif rel["via_relation"] == "HAS_FORMULA" or rel_node.get("kind") == "formula":
                _unique_append(formulas, {"node_id": rel["node_id"], **rel_item}, key="node_id")
            elif rel["via_relation"] == "USED_IN_PROBLEM_TYPE" or rel_node.get("kind") == "problem_type":
                _unique_append(problem_types, {"node_id": rel["node_id"], **rel_item}, key="node_id")
            elif rel["via_relation"] == "RELATED_TO":
                _unique_append(related, {"node_id": rel["node_id"], **rel_item}, key="node_id")

    source_quote_input = matched_nodes + [{"node": item["node"]} for item in supporting_nodes if item.get("node")]
    return {
        "query": query,
        "intent": intent,
        "retrieval": {
            "method": "lexical_fuzzy_graph_expansion",
            "vector_backend": None,
            "limit": limit,
            "neighbor_depth": neighbor_depth,
        },
        "matched_nodes": matched_nodes,
        "supporting_nodes": supporting_nodes,
        "prerequisites": prerequisites,
        "formulas": formulas,
        "problem_types": problem_types,
        "related": related,
        "source_quotes": _source_quotes(source_quote_input, limit=limit),
    }
