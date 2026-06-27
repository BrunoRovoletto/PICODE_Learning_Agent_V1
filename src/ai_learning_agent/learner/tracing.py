"""Mastery tracing.

Reuses the proven Jali/OpenTutor idea: Bayesian Knowledge Tracing (BKT) as the
main update rule, with a simple linear fallback for very small MVP loops.
"""

from __future__ import annotations

from dataclasses import replace

from .models import (
    GapType,
    LearnerNodeState,
    LearnerProfile,
    MasteryMode,
    MasteryUpdateResult,
    PracticeObservation,
    target_difficulty_for_mastery,
)
from .spaced_repetition import apply_review_update


def update_bkt(state: LearnerNodeState, correct: bool) -> float:
    """Return updated P(known) using classic BKT Bayes update."""
    p_l = state.bkt_p_known if state.bkt_p_known is not None else max(state.mastery, 0.10)
    p_t = state.bkt_p_learn
    p_s = state.bkt_p_slip
    p_g = state.bkt_p_guess

    if correct:
        p_obs = p_l * (1 - p_s) + (1 - p_l) * p_g
        posterior = (p_l * (1 - p_s)) / max(p_obs, 1e-9)
    else:
        p_obs = p_l * p_s + (1 - p_l) * (1 - p_g)
        posterior = (p_l * p_s) / max(p_obs, 1e-9)

    # Learning can happen during the attempt.
    p_new = posterior + (1 - posterior) * p_t
    return max(0.01, min(0.99, p_new))


def update_linear(state: LearnerNodeState, correct: bool, correct_delta: float = 0.15, wrong_delta: float = 0.10) -> float:
    delta = correct_delta if correct else -wrong_delta
    return max(0.0, min(1.0, state.mastery + delta))


def diagnose_gap(previous_mastery: float, new_mastery: float, correct: bool, threshold: float) -> GapType | None:
    """OpenTutor-inspired gap classification."""
    if new_mastery >= threshold:
        return "mastered"
    if correct:
        return None
    if previous_mastery < 0.4:
        return "fundamental_gap"
    if previous_mastery < 0.7:
        return "transfer_gap"
    return "trap_vulnerability"


def confidence_from_attempts(attempts: int) -> float:
    # More observations => more confidence, capped conservatively.
    return min(0.95, attempts / 8.0)


class MasteryTracer:
    """Update learner overlay state from practice observations."""

    def __init__(self, mode: MasteryMode = "bkt", mastery_threshold: float = 0.8) -> None:
        self.mode = mode
        self.mastery_threshold = mastery_threshold

    def update_state(self, state: LearnerNodeState, observation: PracticeObservation) -> tuple[LearnerNodeState, MasteryUpdateResult]:
        previous = state.mastery
        attempts = state.attempts + 1
        correct_attempts = state.correct_attempts + (1 if observation.correct else 0)
        streak = state.streak + 1 if observation.correct else 0

        if self.mode == "linear":
            new_mastery = update_linear(state, observation.correct)
            bkt_p_known = state.bkt_p_known
        else:
            bkt_p_known = update_bkt(state, observation.correct)
            new_mastery = bkt_p_known

        gap_type = diagnose_gap(previous, new_mastery, observation.correct, self.mastery_threshold)
        mistakes = list(state.common_mistakes)
        if observation.mistake and observation.mistake not in mistakes:
            mistakes.append(observation.mistake)

        metadata = dict(state.metadata)
        metadata["last_observation"] = {
            "item_id": observation.item_id,
            "session_id": observation.session_id,
            "question_type": observation.question_type,
            "response_time_ms": observation.response_time_ms,
            "confidence": observation.confidence,
            "quality": observation.quality,
            **observation.metadata,
        }

        new_state = replace(
            state,
            mastery=new_mastery,
            confidence=confidence_from_attempts(attempts),
            attempts=attempts,
            correct_attempts=correct_attempts,
            streak=streak,
            last_attempt_at=observation.timestamp,
            bkt_p_known=bkt_p_known,
            gap_type=gap_type,
            common_mistakes=mistakes,
            metadata=metadata,
        )
        if observation.quality is not None:
            new_state = apply_review_update(new_state, observation.quality)

        result = MasteryUpdateResult(
            node_id=state.node_id,
            previous_mastery=previous,
            new_mastery=new_mastery,
            is_mastered=new_mastery >= self.mastery_threshold,
            target_difficulty=target_difficulty_for_mastery(new_mastery),
            gap_type=gap_type,
            attempts=attempts,
            correct_attempts=correct_attempts,
            bkt_p_known=bkt_p_known,
        )
        return new_state, result

    def update_profile(self, profile: LearnerProfile, observation: PracticeObservation) -> tuple[LearnerProfile, MasteryUpdateResult]:
        state = profile.get_state(observation.node_id)
        new_state, result = self.update_state(state, observation)
        return profile.with_state(new_state), result
