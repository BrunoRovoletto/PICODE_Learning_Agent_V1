"""Informal learner memory, separate from formal KG mastery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_learning_agent.learner.models import utc_now_iso

DEFAULT_MEMORY: dict[str, Any] = {
    "schema": "ai_learning_agent.learner_memory.v1",
    "learning_style": {
        "prefers": [],
        "avoid": [],
    },
    "current_constraints": {},
    "recurring_difficulties": [],
    "recent_notes": [],
    "session_summaries": [],
    "metadata": {},
}


def _fresh_memory() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_MEMORY))


def get_user_memory(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        memory = _fresh_memory()
        now = utc_now_iso()
        memory["created_at"] = now
        memory["updated_at"] = now
        return memory
    data = json.loads(path.read_text(encoding="utf-8"))
    memory = _fresh_memory()
    _deep_merge(memory, data)
    memory.setdefault("created_at", utc_now_iso())
    memory.setdefault("updated_at", memory["created_at"])
    return memory


def write_user_memory(memory: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def _merge_lists(old: list[Any], new: list[Any], max_items: int = 25) -> list[Any]:
    result = list(old)
    for item in new:
        if item not in result:
            result.append(item)
    return result[-max_items:]


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if value is None:
            base.pop(key, None)
        elif isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        elif isinstance(value, list) and isinstance(base.get(key), list):
            base[key] = _merge_lists(base[key], value)
        else:
            base[key] = value
    return base


def update_user_memory(path: str | Path, memory_patch: dict[str, Any]) -> dict[str, Any]:
    memory = get_user_memory(path)
    _deep_merge(memory, dict(memory_patch))
    memory["updated_at"] = utc_now_iso()
    write_user_memory(memory, path)
    return memory
