"""JSON persistence for learner profiles."""

from __future__ import annotations

import json
from pathlib import Path

from .models import LearnerProfile


def read_profile_json(path: str | Path, learner_id: str = "default") -> LearnerProfile:
    path = Path(path)
    if not path.exists():
        return LearnerProfile(learner_id=learner_id)
    return LearnerProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_profile_json(profile: LearnerProfile, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
