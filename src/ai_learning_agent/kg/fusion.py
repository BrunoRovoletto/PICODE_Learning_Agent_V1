"""Graphusion-style concept fusion.

This module reimplements the useful part of OpenTutor's LOOM extraction:
extract concepts per chunk, then fuse duplicate concepts across chunks/books
before creating canonical graph nodes.

The implementation is dependency-free by default, but exposes an EmbeddingModel
protocol so a future local model can provide true embedding similarity.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

from .dedupe import lexical_similarity
from .models import ExtractedConcept


class EmbeddingModel(Protocol):
    """Minimal embedding interface for semantic fusion."""

    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for the given text."""


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class FusionReport:
    input_count: int
    output_count: int
    groups_merged: int
    concepts_merged: int
    method: str


@dataclass
class FusionResult:
    concepts: list[ExtractedConcept]
    report: FusionReport


class ConceptFusion:
    """Fuse duplicate extracted concepts before graph building.

    This mirrors OpenTutor's Graphusion-inspired stage:

    1. compare concept `name: description` representations;
    2. group near-duplicates;
    3. keep the most descriptive concept as canonical;
    4. union prerequisites, related concepts, formulas, problem types, aliases.
    """

    def __init__(
        self,
        embedding_model: EmbeddingModel | None = None,
        embedding_threshold: float = 0.85,
        lexical_threshold: float = 0.86,
    ) -> None:
        self.embedding_model = embedding_model
        self.embedding_threshold = embedding_threshold
        self.lexical_threshold = lexical_threshold

    def fuse(self, concepts: list[ExtractedConcept]) -> FusionResult:
        if len(concepts) <= 1:
            return FusionResult(
                concepts=concepts,
                report=FusionReport(len(concepts), len(concepts), 0, 0, self._method_name()),
            )

        groups = self._find_groups(concepts)
        if not groups:
            return FusionResult(
                concepts=concepts,
                report=FusionReport(len(concepts), len(concepts), 0, 0, self._method_name()),
            )

        fused: list[ExtractedConcept] = []
        merged_indices: set[int] = set()
        for group_indices in groups:
            group = [concepts[i] for i in group_indices]
            fused.append(self._merge_group(group))
            merged_indices.update(group_indices)

        for i, concept in enumerate(concepts):
            if i not in merged_indices:
                fused.append(concept)

        return FusionResult(
            concepts=fused,
            report=FusionReport(
                input_count=len(concepts),
                output_count=len(fused),
                groups_merged=len(groups),
                concepts_merged=len(merged_indices),
                method=self._method_name(),
            ),
        )

    def _method_name(self) -> str:
        return "embedding" if self.embedding_model else "lexical"

    def _find_groups(self, concepts: list[ExtractedConcept]) -> list[list[int]]:
        n = len(concepts)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            pa, pb = find(a), find(b)
            if pa != pb:
                parent[pa] = pb

        embeddings: dict[int, list[float]] = {}
        if self.embedding_model:
            for i, concept in enumerate(concepts):
                text = self._concept_text(concept)
                try:
                    embeddings[i] = self.embedding_model.embed(text)
                except Exception:
                    # Fallback to lexical comparison for this concept.
                    pass

        for i in range(n):
            for j in range(i + 1, n):
                if i in embeddings and j in embeddings:
                    score = cosine_similarity(embeddings[i], embeddings[j])
                    threshold = self.embedding_threshold
                else:
                    score = lexical_similarity(concepts[i].name, concepts[j].name)
                    threshold = self.lexical_threshold
                if score >= threshold:
                    union(i, j)

        grouped: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            grouped[find(i)].append(i)
        return [group for group in grouped.values() if len(group) > 1]

    def _merge_group(self, group: list[ExtractedConcept]) -> ExtractedConcept:
        canonical = max(group, key=lambda c: len(c.description or ""))
        merged = ExtractedConcept(
            name=canonical.name,
            description=canonical.description,
            bloom_level=canonical.bloom_level,
            confidence=max(c.confidence for c in group),
            evidence=canonical.evidence,
            metadata=dict(canonical.metadata),
        )
        merged.prerequisites = self._unique(x for c in group for x in c.prerequisites if x != canonical.name)
        merged.related = self._unique(x for c in group for x in c.related if x != canonical.name)
        merged.formulas = self._unique(x for c in group for x in c.formulas)
        merged.problem_types = self._unique(x for c in group for x in c.problem_types)
        merged.aliases = self._unique(
            x
            for c in group
            for x in [c.name, *c.aliases]
            if x and x != canonical.name
        )
        # Keep metadata simple and serializable.
        merged.metadata["fusion_group_size"] = len(group)
        merged.metadata["fusion_aliases"] = merged.aliases
        return merged

    @staticmethod
    def _concept_text(concept: ExtractedConcept) -> str:
        return f"{concept.name}: {concept.description}"

    @staticmethod
    def _unique(items) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            text = str(item).strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
        return result
