"""Prerequisite-aware learning paths, inspired by Jali's PathGenerator."""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_learning_agent.kg.models import KnowledgeNode

from .graph_adapter import KnowledgeGraphLearningAdapter, node_difficulty, node_mastery_threshold
from .models import LearnerProfile


@dataclass(frozen=True)
class LearningPathStep:
    node_id: str
    label: str
    kind: str
    mastery: float
    threshold: float
    estimated_minutes: int
    difficulty: float


@dataclass(frozen=True)
class LearningSession:
    ordinal: int
    estimated_minutes: int
    steps: list[LearningPathStep] = field(default_factory=list)


@dataclass(frozen=True)
class LearningPath:
    target_id: str
    target_label: str
    steps: list[LearningPathStep]
    sessions: list[LearningSession]
    total_minutes: int


class PathGenerator:
    def __init__(self, adapter: KnowledgeGraphLearningAdapter) -> None:
        self.adapter = adapter

    def generate_path(
        self,
        target_id: str,
        profile: LearnerProfile,
        session_minutes: int = 35,
        include_review: bool = False,
        max_steps: int | None = None,
    ) -> LearningPath | None:
        target = self.adapter.get_node(target_id)
        if not target:
            return None

        candidates = self.adapter.transitive_prerequisites_of(target_id) + [target]
        candidates = self._filter_unmastered(candidates, profile, include_review=include_review)
        ordered = self._topological_sort(candidates)
        if max_steps is not None:
            ordered = ordered[:max_steps]
        steps = [self._step(node, profile) for node in ordered]
        sessions = self._group_sessions(steps, session_minutes=session_minutes)
        return LearningPath(
            target_id=target.id,
            target_label=target.label,
            steps=steps,
            sessions=sessions,
            total_minutes=sum(step.estimated_minutes for step in steps),
        )

    def _filter_unmastered(self, nodes: list[KnowledgeNode], profile: LearnerProfile, include_review: bool) -> list[KnowledgeNode]:
        result: list[KnowledgeNode] = []
        seen: set[str] = set()
        for node in nodes:
            if node.id in seen:
                continue
            seen.add(node.id)
            mastery = profile.get_state(node.id).mastery
            threshold = 1.0 if include_review else node_mastery_threshold(node)
            if mastery < threshold:
                result.append(node)
        return result

    def _topological_sort(self, nodes: list[KnowledgeNode]) -> list[KnowledgeNode]:
        node_ids = {node.id for node in nodes}
        node_by_id = {node.id: node for node in nodes}
        visited: set[str] = set()
        result: list[KnowledgeNode] = []

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            for prereq in self.adapter.prerequisites_of(node_id):
                if prereq.id in node_ids:
                    visit(prereq.id)
            if node_id in node_by_id:
                result.append(node_by_id[node_id])

        for node in nodes:
            visit(node.id)
        return result

    @staticmethod
    def _step(node: KnowledgeNode, profile: LearnerProfile) -> LearningPathStep:
        estimated = int(node.properties.get("estimated_minutes", 15) or 15)
        return LearningPathStep(
            node_id=node.id,
            label=node.label,
            kind=node.kind,
            mastery=profile.get_state(node.id).mastery,
            threshold=node_mastery_threshold(node),
            estimated_minutes=max(3, estimated),
            difficulty=node_difficulty(node),
        )

    @staticmethod
    def _group_sessions(steps: list[LearningPathStep], session_minutes: int) -> list[LearningSession]:
        sessions: list[LearningSession] = []
        current: list[LearningPathStep] = []
        total = 0
        ordinal = 0
        for step in steps:
            if current and total + step.estimated_minutes > session_minutes:
                sessions.append(LearningSession(ordinal=ordinal, estimated_minutes=total, steps=current))
                ordinal += 1
                current = []
                total = 0
            current.append(step)
            total += step.estimated_minutes
        if current:
            sessions.append(LearningSession(ordinal=ordinal, estimated_minutes=total, steps=current))
        return sessions
