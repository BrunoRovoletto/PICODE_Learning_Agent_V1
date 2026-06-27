"""Simple exercise index and search for exam-first practice."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable

from ai_learning_agent.kg.models import KnowledgeGraph
from ai_learning_agent.learner.graph_adapter import node_mastery_threshold
from ai_learning_agent.learner.models import LearnerProfile

from .kg_queries import node_to_packet, normalize_text, resolve_node


@dataclass(frozen=True)
class Exercise:
    exercise_id: str
    statement: str
    source_path: str | None = None
    source_doc_id: str | None = None
    page: int | None = None
    required_node_ids: list[str] = field(default_factory=list)
    problem_type: str | None = None
    difficulty: float = 0.3
    number_of_steps: int = 1
    algebra_load: float = 0.2
    has_trap: bool = False
    trap_flags: list[str] = field(default_factory=list)
    exercise_ladder_level: str = "direct_formula"
    solution_available: bool = False
    solution: str | None = None
    source_priority: str = "course"
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Exercise":
        return Exercise(
            exercise_id=str(data.get("exercise_id") or data.get("id")),
            statement=str(data.get("statement", "")),
            source_path=data.get("source_path"),
            source_doc_id=data.get("source_doc_id") or data.get("doc_id"),
            page=data.get("page"),
            required_node_ids=[str(x) for x in data.get("required_node_ids", data.get("concepts", []))],
            problem_type=data.get("problem_type"),
            difficulty=float(data.get("difficulty", 0.3) or 0.3),
            number_of_steps=int(data.get("number_of_steps", data.get("steps", 1)) or 1),
            algebra_load=float(data.get("algebra_load", 0.2) or 0.2),
            has_trap=bool(data.get("has_trap", False)),
            trap_flags=[str(x) for x in data.get("trap_flags", [])],
            exercise_ladder_level=str(data.get("exercise_ladder_level", "direct_formula")),
            solution_available=bool(data.get("solution_available", bool(data.get("solution")))),
            solution=data.get("solution"),
            source_priority=str(data.get("source_priority", "course")),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    def to_dict(self, *, include_solution: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if not include_solution:
            data.pop("solution", None)
        return data


def read_exercises_jsonl(path: str | Path) -> list[Exercise]:
    path = Path(path)
    if not path.exists():
        return []
    exercises: list[Exercise] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                exercises.append(Exercise.from_dict(json.loads(line)))
    return exercises


def write_exercises_jsonl(exercises: Iterable[Exercise], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for exercise in exercises:
            handle.write(json.dumps(exercise.to_dict(include_solution=True), ensure_ascii=False) + "\n")


def _difficulty_matches(exercise: Exercise, difficulty: str | float | None) -> bool:
    if difficulty is None:
        return True
    if isinstance(difficulty, int | float):
        return abs(exercise.difficulty - float(difficulty)) <= 0.20
    band = str(difficulty).lower()
    if band == "easy":
        return exercise.difficulty <= 0.45
    if band == "medium":
        return 0.30 <= exercise.difficulty <= 0.75
    if band == "hard":
        return exercise.difficulty >= 0.60
    return True


def _unmastered_required_count(exercise: Exercise, graph: KnowledgeGraph | None, profile: LearnerProfile | None) -> int:
    if graph is None or profile is None:
        return 0
    count = 0
    for node_id in exercise.required_node_ids:
        node = graph.nodes.get(node_id)
        if node is None:
            continue
        if profile.get_state(node_id).mastery < node_mastery_threshold(node):
            count += 1
    return count


def _query_score(exercise: Exercise, query: str | None) -> float:
    if not query:
        return 0.0
    q = normalize_text(query)
    hay = normalize_text(
        " ".join(
            [
                exercise.statement,
                exercise.problem_type or "",
                exercise.exercise_ladder_level,
                exercise.source_path or "",
                " ".join(exercise.required_node_ids),
                " ".join(exercise.trap_flags),
            ]
        )
    )
    if q in hay:
        return 0.5
    q_tokens = set(q.split())
    h_tokens = set(hay.split())
    return 0.35 * len(q_tokens & h_tokens) / max(1, len(q_tokens))


def search_exercises(
    exercises: list[Exercise],
    *,
    query: str | None = None,
    target_nodes: Iterable[str] | None = None,
    graph: KnowledgeGraph | None = None,
    profile: LearnerProfile | None = None,
    difficulty: str | float | None = None,
    max_new_concepts: int | None = 1,
    source_priority: str | None = "course",
    ladder_level: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    target_ids: set[str] = set()
    for target in target_nodes or []:
        resolved = resolve_node(graph, target) if graph is not None else None
        target_ids.add(resolved.id if resolved else str(target))

    results: list[dict[str, Any]] = []
    for exercise in exercises:
        if target_ids and not (target_ids & set(exercise.required_node_ids)):
            continue
        if not _difficulty_matches(exercise, difficulty):
            continue
        if ladder_level and exercise.exercise_ladder_level != ladder_level:
            continue
        new_count = _unmastered_required_count(exercise, graph, profile)
        if max_new_concepts is not None and new_count > max_new_concepts:
            continue
        score = _query_score(exercise, query)
        if target_ids:
            score += 0.45
        if source_priority and exercise.source_priority == source_priority:
            score += 0.20
        score += max(0.0, 1.0 - exercise.difficulty) * 0.10
        score -= max(0, exercise.number_of_steps - 1) * 0.02
        results.append(
            {
                "score": round(score, 4),
                "new_concepts": new_count,
                "exercise": exercise.to_dict(include_solution=False),
            }
        )
    results.sort(key=lambda item: (-item["score"], item["exercise"]["difficulty"], item["exercise"]["exercise_id"]))
    return results[:limit]


def get_exercise(
    exercises: list[Exercise],
    exercise_id: str,
    *,
    graph: KnowledgeGraph | None = None,
    profile: LearnerProfile | None = None,
    include_solution: bool = False,
    include_context: bool = True,
) -> dict[str, Any]:
    exercise = next((item for item in exercises if item.exercise_id == exercise_id), None)
    if exercise is None:
        return {"found": False, "exercise_id": exercise_id}
    packet: dict[str, Any] = {"found": True, "exercise": exercise.to_dict(include_solution=include_solution)}
    if include_context and graph is not None:
        packet["required_nodes"] = [
            node_to_packet(graph.nodes[node_id], profile=profile, include_sources=True)
            for node_id in exercise.required_node_ids
            if node_id in graph.nodes
        ]
    return packet
