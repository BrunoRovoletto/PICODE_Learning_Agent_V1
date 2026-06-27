"""SM-2-style spaced repetition for learner node states.

This is intentionally close to Jali's scheduling mechanism, but expressed in
small dependency-free Python dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from .models import LearnerNodeState, utc_now_iso

MIN_EASINESS = 1.3
MAX_EASINESS = 2.5
DEFAULT_EASINESS = 2.5
INITIAL_INTERVAL_DAYS = 1
SECOND_INTERVAL_DAYS = 6


@dataclass(frozen=True)
class ReviewUpdate:
    easiness_factor: float
    interval_days: int
    repetitions: int
    next_review_at: str


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def calculate_review_update(state: LearnerNodeState, quality: int, now: datetime | None = None) -> ReviewUpdate:
    """Calculate SM-2 update. Quality is 0-5."""
    quality = max(0, min(5, int(quality)))
    now = now or datetime.now(timezone.utc)
    easiness = state.easiness_factor or DEFAULT_EASINESS
    repetitions = state.repetitions

    if quality >= 3:
        if repetitions == 0:
            interval = INITIAL_INTERVAL_DAYS
        elif repetitions == 1:
            interval = SECOND_INTERVAL_DAYS
        else:
            interval = max(1, round(max(state.interval_days, SECOND_INTERVAL_DAYS) * easiness))
        repetitions += 1
    else:
        repetitions = 0
        interval = INITIAL_INTERVAL_DAYS

    easiness += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    easiness = max(MIN_EASINESS, min(MAX_EASINESS, easiness))
    next_review = now + timedelta(days=interval)
    return ReviewUpdate(
        easiness_factor=easiness,
        interval_days=interval,
        repetitions=repetitions,
        next_review_at=next_review.isoformat(),
    )


def apply_review_update(state: LearnerNodeState, quality: int, now: datetime | None = None) -> LearnerNodeState:
    update = calculate_review_update(state, quality=quality, now=now)
    return replace(
        state,
        easiness_factor=update.easiness_factor,
        interval_days=update.interval_days,
        repetitions=update.repetitions,
        next_review_at=update.next_review_at,
    )


def is_due(state: LearnerNodeState, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    due = _parse_iso(state.next_review_at)
    if due is None:
        return state.attempts > 0
    return due <= now


def review_priority(state: LearnerNodeState, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    due = _parse_iso(state.next_review_at)
    if due is None:
        return 1.0 if state.attempts > 0 else 0.0
    overdue_days = (now - due).total_seconds() / 86400.0
    mastery_factor = 1 - state.mastery * 0.3
    return overdue_days * mastery_factor * 10


def quality_to_mastery_adjustment(quality: int) -> float:
    return {5: 0.10, 4: 0.05, 3: 0.0, 2: -0.10, 1: -0.20, 0: -0.30}[max(0, min(5, int(quality)))]
