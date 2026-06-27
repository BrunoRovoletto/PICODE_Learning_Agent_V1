"""Append-only attempt log for practice evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ai_learning_agent.learner.models import utc_now_iso


def _attempt_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return "attempt:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def record_attempt(path: str | Path, attempt_json: dict[str, Any]) -> dict[str, Any]:
    """Append one raw user attempt and return the stored record.

    This records evidence only. Mastery changes happen later through
    update_learner(assessment_json).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = utc_now_iso()
    record = {
        "schema": "ai_learning_agent.attempt.v1",
        "timestamp": timestamp,
        **dict(attempt_json),
    }
    record.setdefault("attempt_id", _attempt_id(record))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_attempts(path: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    if limit is not None:
        return records[-limit:]
    return records


def recent_mistakes_from_attempts(path: str | Path, *, limit: int = 8) -> list[str]:
    mistakes: list[str] = []
    for attempt in read_attempts(path, limit=limit):
        for key in ("mistake", "mistakes", "self_reported_difficulty"):
            value = attempt.get(key)
            if isinstance(value, str) and value and value not in mistakes:
                mistakes.append(value)
            elif isinstance(value, list):
                for item in value:
                    text = str(item).strip()
                    if text and text not in mistakes:
                        mistakes.append(text)
    return mistakes[-limit:]
