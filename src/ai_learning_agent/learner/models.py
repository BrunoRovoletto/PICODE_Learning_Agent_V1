"""Learner-state models.

This brick follows Jali's best idea: keep the canonical knowledge graph clean and
store a learner-specific overlay keyed by KG node id. The overlay can render as a
"mirror KG" without duplicating graph structure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

GapType = Literal["fundamental_gap", "transfer_gap", "trap_vulnerability", "mastered"]
DifficultyBand = Literal["easy", "medium", "hard"]
MasteryMode = Literal["bkt", "linear"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PracticeObservation:
    """One observed learning/practice event for a KG node."""

    node_id: str
    correct: bool
    timestamp: str = field(default_factory=utc_now_iso)
    confidence: float | None = None
    response_time_ms: int | None = None
    item_id: str | None = None
    session_id: str | None = None
    question_type: str | None = None
    quality: int | None = None  # 0-5 recall quality for spaced repetition
    mistake: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearnerNodeState:
    """Learner overlay for one canonical KG node."""

    node_id: str
    mastery: float = 0.0
    confidence: float = 0.0
    attempts: int = 0
    correct_attempts: int = 0
    streak: int = 0
    last_attempt_at: str | None = None

    # BKT state/params, matching the Jali/OpenTutor pattern.
    bkt_p_known: float | None = None
    bkt_p_learn: float = 0.20
    bkt_p_slip: float = 0.10
    bkt_p_guess: float = 0.25

    # Adaptive diagnosis, inspired by OpenTutor.
    gap_type: GapType | None = None
    common_mistakes: list[str] = field(default_factory=list)

    # SM-2-style review state, inspired by Jali.
    easiness_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    next_review_at: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        return self.correct_attempts / self.attempts if self.attempts else 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "LearnerNodeState":
        return LearnerNodeState(
            node_id=data["node_id"],
            mastery=float(data.get("mastery", 0.0)),
            confidence=float(data.get("confidence", 0.0)),
            attempts=int(data.get("attempts", 0)),
            correct_attempts=int(data.get("correct_attempts", 0)),
            streak=int(data.get("streak", 0)),
            last_attempt_at=data.get("last_attempt_at"),
            bkt_p_known=(float(data["bkt_p_known"]) if data.get("bkt_p_known") is not None else None),
            bkt_p_learn=float(data.get("bkt_p_learn", 0.20)),
            bkt_p_slip=float(data.get("bkt_p_slip", 0.10)),
            bkt_p_guess=float(data.get("bkt_p_guess", 0.25)),
            gap_type=data.get("gap_type"),
            common_mistakes=list(data.get("common_mistakes", [])),
            easiness_factor=float(data.get("easiness_factor", 2.5)),
            interval_days=int(data.get("interval_days", 0)),
            repetitions=int(data.get("repetitions", 0)),
            next_review_at=data.get("next_review_at"),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass(frozen=True)
class LearnerProfile:
    """Complete learner overlay for one user."""

    learner_id: str = "default"
    node_states: dict[str, LearnerNodeState] = field(default_factory=dict)
    overall_ability: float = 0.0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_state(self, node_id: str) -> LearnerNodeState:
        return self.node_states.get(node_id, LearnerNodeState(node_id=node_id))

    def with_state(self, state: LearnerNodeState) -> "LearnerProfile":
        states = dict(self.node_states)
        states[state.node_id] = state
        return LearnerProfile(
            learner_id=self.learner_id,
            node_states=states,
            overall_ability=_compute_overall_ability(states),
            created_at=self.created_at,
            updated_at=utc_now_iso(),
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ai_learning_agent.learner.v1",
            "learner_id": self.learner_id,
            "node_states": {node_id: state.to_dict() for node_id, state in sorted(self.node_states.items())},
            "overall_ability": self.overall_ability,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "LearnerProfile":
        states = {
            node_id: LearnerNodeState.from_dict(state)
            for node_id, state in dict(data.get("node_states", {}) or {}).items()
        }
        return LearnerProfile(
            learner_id=data.get("learner_id", "default"),
            node_states=states,
            overall_ability=float(data.get("overall_ability", _compute_overall_ability(states))),
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass(frozen=True)
class MasteryUpdateResult:
    node_id: str
    previous_mastery: float
    new_mastery: float
    is_mastered: bool
    target_difficulty: DifficultyBand
    gap_type: GapType | None
    attempts: int
    correct_attempts: int
    bkt_p_known: float | None = None


@dataclass(frozen=True)
class LearnerGraphNodeView:
    """One node in the dynamic mirror graph view."""

    node_id: str
    label: str
    kind: str
    mastery: float
    status: Literal["unknown", "fragile", "learning", "mastered"]
    gap_type: GapType | None = None
    blocked_by: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)


def _compute_overall_ability(states: dict[str, LearnerNodeState]) -> float:
    if not states:
        return 0.0
    # Jali-style weighted estimate: high-mastery states are more reliable.
    total_weight = 0.0
    weighted = 0.0
    for state in states.values():
        weight = max(0.05, state.mastery)
        total_weight += weight
        weighted += state.mastery * weight
    return weighted / total_weight if total_weight else 0.0


def mastery_status(mastery: float, threshold: float = 0.8) -> Literal["unknown", "fragile", "learning", "mastered"]:
    if mastery >= threshold:
        return "mastered"
    if mastery <= 0.05:
        return "unknown"
    if mastery < 0.4:
        return "fragile"
    return "learning"


def target_difficulty_for_mastery(mastery: float) -> DifficultyBand:
    if mastery < 0.4:
        return "easy"
    if mastery <= 0.7:
        return "medium"
    return "hard"
