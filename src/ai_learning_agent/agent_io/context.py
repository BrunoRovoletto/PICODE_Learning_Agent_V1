"""Teaching context packer for Pi calls."""

from __future__ import annotations

import json
from typing import Any

from ai_learning_agent.kg.models import KnowledgeGraph
from ai_learning_agent.learner.models import LearnerProfile

from .exercises import Exercise, get_exercise
from .kg_queries import resolve_node
from .learner_tools import get_learning_path, get_proximal_dev
from .retrieval import context_retrieve

MODE_ALLOWED_ACTIONS: dict[str, list[str]] = {
    "guided_exercise": ["ask_question", "give_hint", "evaluate_attempt", "request_more_context", "update_memory"],
    "concept_repair": ["explain_visually", "ask_micro_question", "give_tiny_exercise", "evaluate_attempt", "update_memory"],
    "exam_sprint": ["choose_high_value_exercise", "give_minimal_hint", "evaluate_attempt", "move_on_or_repair"],
    "review": ["ask_recall", "check_due_review", "evaluate_attempt", "schedule_review"],
    "burnout_mode": ["reduce_scope", "give_one_small_step", "encourage", "pause_or_continue", "update_memory"],
}


def _profile_mistakes(profile: LearnerProfile | None, limit: int = 8) -> list[str]:
    if profile is None:
        return []
    mistakes: list[str] = []
    states = sorted(profile.node_states.values(), key=lambda state: state.last_attempt_at or "", reverse=True)
    for state in states:
        for mistake in state.common_mistakes:
            if mistake and mistake not in mistakes:
                mistakes.append(mistake)
                if len(mistakes) >= limit:
                    return mistakes
    return mistakes


def _trim_packet(packet: dict[str, Any], token_budget: int) -> dict[str, Any]:
    """Approximate token budget trimming without tokenizer dependency."""
    char_budget = max(1000, int(token_budget) * 4)
    if len(json.dumps(packet, ensure_ascii=False)) <= char_budget:
        return packet

    # Trim largest/contextual lists first while preserving structure.
    for path in [
        ("retrieval", "source_quotes"),
        ("retrieval", "supporting_nodes"),
        ("retrieval", "matched_nodes"),
        ("zpd_snapshot", "blocked"),
        ("zpd_snapshot", "zpd"),
    ]:
        current: Any = packet
        for key in path[:-1]:
            current = current.get(key, {}) if isinstance(current, dict) else {}
        key = path[-1]
        if isinstance(current, dict) and isinstance(current.get(key), list):
            current[key] = current[key][: max(1, len(current[key]) // 2)]
            if len(json.dumps(packet, ensure_ascii=False)) <= char_budget:
                return packet
    packet["trimmed_to_budget"] = True
    return packet


def pack_teaching_context(
    graph: KnowledgeGraph,
    *,
    profile: LearnerProfile | None = None,
    user_memory: dict[str, Any] | None = None,
    exercises: list[Exercise] | None = None,
    mode: str = "guided_exercise",
    exercise_id: str | None = None,
    target_node: str | None = None,
    query: str | None = None,
    token_budget: int = 3000,
) -> dict[str, Any]:
    exercise_packet: dict[str, Any] | None = None
    retrieval_query = query
    target_for_path = target_node

    if exercise_id and exercises is not None:
        exercise_packet = get_exercise(exercises, exercise_id, graph=graph, profile=profile, include_solution=False, include_context=True)
        exercise = exercise_packet.get("exercise", {}) if exercise_packet.get("found") else {}
        retrieval_query = retrieval_query or exercise.get("statement")
        if not target_for_path and exercise.get("required_node_ids"):
            target_for_path = exercise["required_node_ids"][-1]

    if not retrieval_query and target_node:
        resolved = resolve_node(graph, target_node)
        retrieval_query = resolved.label if resolved else target_node
    if not retrieval_query:
        retrieval_query = ""

    retrieval = context_retrieve(graph, retrieval_query, profile=profile, intent=mode, limit=6) if retrieval_query else None
    zpd_snapshot = get_proximal_dev(graph, profile, max_results=5, mode=mode) if profile is not None else None
    learning_path = (
        get_learning_path(graph, profile, goal_node=target_for_path, mode=mode, max_steps=8, session_minutes=20)
        if profile is not None and target_for_path
        else None
    )

    memory = user_memory or {}
    recent_mistakes = _profile_mistakes(profile)
    for item in memory.get("recurring_difficulties", []) if isinstance(memory, dict) else []:
        text = str(item).strip()
        if text and text not in recent_mistakes:
            recent_mistakes.append(text)

    packet = {
        "schema": "ai_learning_agent.teaching_context.v1",
        "mode": mode,
        "objective": {
            "query": query,
            "target_node": target_node,
            "exercise_id": exercise_id,
        },
        "exercise": exercise_packet,
        "retrieval": retrieval,
        "zpd_snapshot": zpd_snapshot,
        "learning_path": learning_path,
        "recent_mistakes": recent_mistakes[:8],
        "user_memory": memory,
        "allowed_actions": MODE_ALLOWED_ACTIONS.get(mode, MODE_ALLOWED_ACTIONS["guided_exercise"]),
        "architecture_note": "one canonical teacher KG plus learner overlay; learner KG is a dynamic view",
    }
    return _trim_packet(packet, token_budget=token_budget)
