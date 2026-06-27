"""Jali-style Zone of Proximal Development over our KG."""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_learning_agent.kg.models import KnowledgeNode

from .graph_adapter import KnowledgeGraphLearningAdapter, node_difficulty, node_mastery_threshold
from .models import LearnerGraphNodeView, LearnerProfile, mastery_status


@dataclass(frozen=True)
class ZPDCandidate:
    node_id: str
    label: str
    kind: str
    mastery: float
    threshold: float
    difficulty: float
    score: float
    reason: str
    unmet_prerequisites: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ZPDResult:
    ready: list[ZPDCandidate]
    zpd: list[ZPDCandidate]
    blocked: list[ZPDCandidate]
    mastered_count: int
    total_trackable: int
    ability_level: float


class ZPDCalculator:
    """Find nodes the learner is ready to learn next.

    Compatible with Jali's approach: a node is ready if it is unmastered, its
    prerequisites are mastered, and its difficulty is near learner ability.
    """

    def __init__(self, adapter: KnowledgeGraphLearningAdapter) -> None:
        self.adapter = adapter

    def calculate(
        self,
        profile: LearnerProfile,
        max_results: int | None = None,
        difficulty_tolerance: float = 0.30,
    ) -> ZPDResult:
        ability = profile.overall_ability if profile.node_states else 0.30
        ready: list[ZPDCandidate] = []
        zpd: list[ZPDCandidate] = []
        blocked: list[ZPDCandidate] = []
        mastered_count = 0
        trackable = self.adapter.trackable_nodes()

        for node in trackable:
            threshold = node_mastery_threshold(node)
            state = profile.get_state(node.id)
            mastery = state.mastery
            difficulty = node_difficulty(node)
            if mastery >= threshold:
                mastered_count += 1
                continue

            unmet = self._unmet_prerequisites(node, profile)
            if unmet:
                blocked.append(
                    self._candidate(node, mastery, threshold, difficulty, score=-1.0, reason="blocked_by_prerequisites", unmet=unmet)
                )
                continue

            candidate = self._candidate(
                node,
                mastery,
                threshold,
                difficulty,
                score=self._priority_score(node, mastery, threshold, difficulty, ability, state_gap=state.gap_type),
                reason="prerequisites_met",
            )
            zpd.append(candidate)
            if difficulty - ability <= difficulty_tolerance:
                ready.append(candidate)

        ready.sort(key=lambda c: c.score, reverse=True)
        zpd.sort(key=lambda c: c.score, reverse=True)
        blocked.sort(key=lambda c: (len(c.unmet_prerequisites), c.difficulty))
        if max_results is not None:
            ready = ready[:max_results]
            zpd = zpd[:max_results]
            blocked = blocked[:max_results]
        return ZPDResult(
            ready=ready,
            zpd=zpd,
            blocked=blocked,
            mastered_count=mastered_count,
            total_trackable=len(trackable),
            ability_level=ability,
        )

    def get_next_node(self, profile: LearnerProfile) -> ZPDCandidate | None:
        result = self.calculate(profile, max_results=1)
        return result.ready[0] if result.ready else (result.zpd[0] if result.zpd else None)

    def mirror_view(self, profile: LearnerProfile) -> list[LearnerGraphNodeView]:
        """Return a dynamic learner KG view without duplicating the KG."""
        views: list[LearnerGraphNodeView] = []
        for node in self.adapter.trackable_nodes():
            threshold = node_mastery_threshold(node)
            state = profile.get_state(node.id)
            unmet = self._unmet_prerequisites(node, profile)
            views.append(
                LearnerGraphNodeView(
                    node_id=node.id,
                    label=node.label,
                    kind=node.kind,
                    mastery=state.mastery,
                    status=mastery_status(state.mastery, threshold),
                    gap_type=state.gap_type,
                    blocked_by=unmet,
                    properties={"difficulty": node_difficulty(node), "mastery_threshold": threshold},
                )
            )
        return views

    def _unmet_prerequisites(self, node: KnowledgeNode, profile: LearnerProfile) -> list[str]:
        unmet: list[str] = []
        for prereq in self.adapter.prerequisites_of(node.id):
            threshold = node_mastery_threshold(prereq)
            mastery = profile.get_state(prereq.id).mastery
            if mastery < threshold:
                unmet.append(prereq.label)
        return unmet

    @staticmethod
    def _candidate(
        node: KnowledgeNode,
        mastery: float,
        threshold: float,
        difficulty: float,
        score: float,
        reason: str,
        unmet: list[str] | None = None,
    ) -> ZPDCandidate:
        return ZPDCandidate(
            node_id=node.id,
            label=node.label,
            kind=node.kind,
            mastery=mastery,
            threshold=threshold,
            difficulty=difficulty,
            score=score,
            reason=reason,
            unmet_prerequisites=unmet or [],
        )

    @staticmethod
    def _priority_score(
        node: KnowledgeNode,
        mastery: float,
        threshold: float,
        difficulty: float,
        ability: float,
        state_gap: str | None,
    ) -> float:
        gap = max(0.0, threshold - mastery)
        closeness = 1.0 - min(1.0, abs(difficulty - ability))
        exam_relevance = float(node.properties.get("exam_relevance", 0.5) or 0.5)
        threshold_bonus = 0.15 if node.properties.get("is_threshold_concept") else 0.0
        gap_bonus = 0.10 if state_gap in {"fundamental_gap", "transfer_gap"} else 0.0
        return gap * 0.45 + closeness * 0.25 + exam_relevance * 0.20 + threshold_bonus + gap_bonus
