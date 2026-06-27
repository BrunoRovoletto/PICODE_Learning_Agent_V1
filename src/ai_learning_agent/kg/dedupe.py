"""Canonicalization and deduplication for KG nodes.

OpenTutor's LOOM mechanism uses Graphusion-style multi-chunk extraction plus
embedding-based fusion. This brick keeps the same design, but starts with a
zero-dependency lexical deduper. Later we can swap in an embedding deduper
without changing the builder interface.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

_STOP_TOKENS = {
    "the",
    "a",
    "an",
    "of",
    "and",
    "di",
    "del",
    "della",
    "delle",
    "dei",
    "degli",
    "la",
    "il",
    "lo",
    "le",
    "i",
    "gli",
    "un",
    "una",
    "s",  # from possessives like Newton's
}


def normalize_label(label: str) -> str:
    """Normalize a node label for ids and matching."""
    label = label.lower().replace("’", "'")
    label = re.sub(r"['’]s\b", "", label)
    label = re.sub(r"[^a-z0-9àèéìòù]+", " ", label)
    tokens = [tok for tok in label.split() if tok not in _STOP_TOKENS]
    return " ".join(tokens).strip()


def stable_node_id(kind: str, label: str) -> str:
    """Create a stable compact id from kind + normalized label."""
    normalized = normalize_label(label)
    digest = hashlib.sha1(f"{kind}:{normalized}".encode("utf-8")).hexdigest()[:12]
    return f"{kind}:{digest}"


def token_set(label: str) -> set[str]:
    return set(normalize_label(label).split())


def lexical_similarity(a: str, b: str) -> float:
    """Simple similarity score in [0, 1] for concept labels."""
    norm_a = normalize_label(a)
    norm_b = normalize_label(b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0
    if norm_a in norm_b or norm_b in norm_a:
        shorter = min(len(norm_a), len(norm_b))
        longer = max(len(norm_a), len(norm_b))
        return max(0.86, shorter / longer)
    ta = token_set(a)
    tb = token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class NodeDeduper(Protocol):
    """Interface for pluggable node fusion."""

    def find_match(self, label: str, candidate_labels: list[str]) -> str | None:
        """Return the matching candidate label, or None."""


@dataclass
class LexicalNodeDeduper:
    """Zero-dependency deduper used for the first brick."""

    threshold: float = 0.86

    def find_match(self, label: str, candidate_labels: list[str]) -> str | None:
        best_label: str | None = None
        best_score = 0.0
        for candidate in candidate_labels:
            score = lexical_similarity(label, candidate)
            if score > best_score:
                best_score = score
                best_label = candidate
        return best_label if best_score >= self.threshold else None
