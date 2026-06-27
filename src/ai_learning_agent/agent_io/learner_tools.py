"""Pi-facing learner commands built on the learner brick."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ai_learning_agent.kg.models import KnowledgeGraph
from ai_learning_agent.learner.graph_adapter import KnowledgeGraphLearningAdapter, node_mastery_threshold
from ai_learning_agent.learner.models import LearnerProfile, PracticeObservation, utc_now_iso
from ai_learning_agent.learner.path import LearningPath, PathGenerator
from ai_learning_agent.learner.tracing import MasteryTracer
from ai_learning_agent.learner.zpd import ZPDCandidate, ZPDCalculator

from .kg_queries import resolve_node


def _candidate_to_dict(candidate: ZPDCandidate, graph: KnowledgeGraph) -> dict[str, Any]:
    node = graph.nodes.get(candidate.node_id)
    props = node.properties if node else {}
    return {
        "node_id": candidate.node_id,
        "label": candidate.label,
        "kind": candidate.kind,
        "mastery": candidate.mastery,
        "threshold": candidate.threshold,
        "difficulty": candidate.difficulty,
        "exam_relevance": float(props.get("exam_relevance", 0.5) or 0.5),
        "score": candidate.score,
        "reason": candidate.reason,
        "unmet_prerequisites": list(candidate.unmet_prerequisites),
        "blocking_prerequisites": list(candidate.unmet_prerequisites),
    }


def get_proximal_dev(
    graph: KnowledgeGraph,
    profile: LearnerProfile,
    *,
    max_results: int = 10,
    mode: str = "exam_sprint",
) -> dict[str, Any]:
    adapter = KnowledgeGraphLearningAdapter(graph)
    result = ZPDCalculator(adapter).calculate(profile, max_results=max_results)
    return {
        "mode": mode,
        "ability": result.ability_level,
        "mastered_count": result.mastered_count,
        "total_trackable": result.total_trackable,
        "ready": [_candidate_to_dict(candidate, graph) for candidate in result.ready],
        "zpd": [_candidate_to_dict(candidate, graph) for candidate in result.zpd],
        "blocked": [_candidate_to_dict(candidate, graph) for candidate in result.blocked],
    }


def _path_to_dict(path: LearningPath) -> dict[str, Any]:
    return {
        "target": {"node_id": path.target_id, "label": path.target_label},
        "total_minutes": path.total_minutes,
        "steps": [asdict(step) for step in path.steps],
        "sessions": [asdict(session) for session in path.sessions],
    }


def get_learning_path(
    graph: KnowledgeGraph,
    profile: LearnerProfile,
    *,
    goal_node: str | None = None,
    mode: str = "exam_sprint",
    max_steps: int = 12,
    session_minutes: int = 25,
) -> dict[str, Any]:
    adapter = KnowledgeGraphLearningAdapter(graph)
    target_id: str | None = None
    chosen_reason = "explicit_goal"
    if goal_node:
        resolved = resolve_node(graph, goal_node)
        target_id = resolved.id if resolved else goal_node
    else:
        zpd = ZPDCalculator(adapter).calculate(profile, max_results=1)
        candidate = zpd.ready[0] if zpd.ready else (zpd.zpd[0] if zpd.zpd else None)
        if candidate:
            target_id = candidate.node_id
            chosen_reason = "top_zpd_candidate"
    if not target_id:
        return {"mode": mode, "found": False, "reason": "no_goal_and_no_zpd_candidate", "paths": []}

    path = PathGenerator(adapter).generate_path(target_id, profile, session_minutes=session_minutes, max_steps=max_steps)
    if path is None:
        return {"mode": mode, "found": False, "reason": "target_not_found", "target_id": target_id, "paths": []}
    return {"mode": mode, "found": True, "chosen_reason": chosen_reason, "path": _path_to_dict(path)}


def _coerce_correct(evaluation: dict[str, Any]) -> bool:
    if "correct" in evaluation:
        return bool(evaluation["correct"])
    if "is_correct" in evaluation:
        return bool(evaluation["is_correct"])
    if "score" in evaluation:
        return float(evaluation["score"] or 0.0) >= 0.6
    if "quality" in evaluation:
        return int(evaluation["quality"] or 0) >= 3
    return False


def update_learner(
    graph: KnowledgeGraph | None,
    profile: LearnerProfile,
    assessment_json: dict[str, Any],
    *,
    mode: str = "bkt",
) -> tuple[LearnerProfile, dict[str, Any]]:
    """Apply deterministic mastery updates from Pi's assessment JSON.

    Pi evaluates evidence and emits node evaluations. This function turns them
    into PracticeObservation objects and applies BKT/linear updates.
    """
    timestamp = utc_now_iso()
    exercise_id = assessment_json.get("exercise_id") or assessment_json.get("item_id")
    session_id = assessment_json.get("session_id")
    updates: list[dict[str, Any]] = []
    current_profile = profile

    for evaluation in assessment_json.get("node_evaluations", []):
        node_ref = str(evaluation.get("node_id") or evaluation.get("node") or "").strip()
        if not node_ref:
            continue
        node = resolve_node(graph, node_ref) if graph is not None else None
        node_id = node.id if node is not None else node_ref
        threshold = node_mastery_threshold(node) if node is not None else 0.8
        tracer = MasteryTracer(mode=mode, mastery_threshold=threshold)
        observation = PracticeObservation(
            node_id=node_id,
            correct=_coerce_correct(evaluation),
            timestamp=timestamp,
            confidence=(float(evaluation["confidence"]) if evaluation.get("confidence") is not None else None),
            response_time_ms=(int(evaluation["response_time_ms"]) if evaluation.get("response_time_ms") is not None else None),
            item_id=str(exercise_id) if exercise_id else None,
            session_id=str(session_id) if session_id else None,
            question_type=evaluation.get("question_type"),
            quality=(int(evaluation["quality"]) if evaluation.get("quality") is not None else None),
            mistake=evaluation.get("mistake"),
            metadata={
                "evidence": evaluation.get("evidence"),
                "assessment_source": assessment_json.get("source", "pi_agent"),
                "raw_evaluation": dict(evaluation),
            },
        )
        previous_state = current_profile.get_state(node_id)
        current_profile, result = tracer.update_profile(current_profile, observation)
        new_state = current_profile.get_state(node_id)
        updates.append(
            {
                "node_id": node_id,
                "label": node.label if node else evaluation.get("label"),
                "previous_mastery": result.previous_mastery,
                "new_mastery": result.new_mastery,
                "mastery_delta": result.new_mastery - result.previous_mastery,
                "is_mastered": result.is_mastered,
                "target_difficulty": result.target_difficulty,
                "gap_type": result.gap_type,
                "attempts": result.attempts,
                "correct_attempts": result.correct_attempts,
                "previous_attempts": previous_state.attempts,
                "last_attempt_at": new_state.last_attempt_at,
                "next_review_at": new_state.next_review_at,
                "bkt_p_known": result.bkt_p_known,
            }
        )

    packet = {
        "schema": "ai_learning_agent.agent_io.learner_update.v1",
        "updated_at": timestamp,
        "learner_id": current_profile.learner_id,
        "exercise_id": exercise_id,
        "session_id": session_id,
        "mode": mode,
        "updates": updates,
        "overall_ability": current_profile.overall_ability,
    }
    return current_profile, packet
