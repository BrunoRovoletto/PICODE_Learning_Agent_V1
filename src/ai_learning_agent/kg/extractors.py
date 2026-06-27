"""Extraction boundary for the KG brick.

The KG builder does not call a model directly. Instead, this module exposes:

1. a Physics-aware prompt builder;
2. a parser for JSON array LLM outputs;
3. a tiny deterministic extractor for smoke tests and demos.

This keeps model/API choices outside the brick.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from .models import ExtractedConcept, SourceChunk


class ConceptExtractor(Protocol):
    """Boundary for any concept extractor implementation."""

    def extract(self, chunk: SourceChunk) -> list[ExtractedConcept]:
        """Return extracted concepts for one source chunk."""


class PhysicsPromptBuilder:
    """Builds the extraction prompt used by external LLM calls.

    Inspired by OpenTutor LOOM extraction, with Physics 1-specific fields.
    """

    SYSTEM = (
        "You are a careful Physics 1 curriculum analyst. "
        "Extract a source-grounded knowledge graph. Output valid JSON only."
    )

    def build_user_prompt(self, chunk: SourceChunk) -> str:
        return f"""
Analyze this Physics 1 book chunk and extract key knowledge-graph concepts.

For each concept, output this JSON object shape:
{{
  "name": "concise concept name, 2-6 words",
  "description": "one sentence grounded in the text",
  "prerequisites": ["concept names needed first"],
  "related": ["closely related concept names"],
  "formulas": ["important formulas exactly as text/LaTeX if present"],
  "problem_types": ["problem families this concept helps solve"],
  "bloom_level": "remember|understand|apply|analyze|evaluate|create",
  "confidence": 0.0,
  "evidence": "short quote from the chunk"
}}

Rules:
- Prefer Physics 1 concepts: kinematics, dynamics, work/energy, momentum,
  rigid bodies, fluids, thermodynamics, oscillations, gravitation.
- Use stable Italian canonical names when possible, but put English/alternate
  book names in `aliases`.
- Include formulas only when the chunk supports them.
- Use prerequisites from the same chunk when possible; otherwise use obvious
  Physics prerequisites only if needed.
- Avoid duplicates and overly broad nodes like "Physics".
- Output a JSON array only. No markdown.

Source title: {chunk.title}
Chunk id: {chunk.chunk_id}

Text:
{chunk.text[:4500]}
""".strip()


class JsonArrayConceptParser:
    """Parse LLM JSON-array output into ExtractedConcept objects."""

    def parse(self, raw: str) -> list[ExtractedConcept]:
        raw = raw.strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start < 0 or end <= start:
            raise ValueError("LLM output does not contain a JSON array")
        payload = json.loads(raw[start:end])
        if not isinstance(payload, list):
            raise ValueError("LLM output JSON is not an array")
        concepts = [ExtractedConcept.from_mapping(item) for item in payload if isinstance(item, dict)]
        return [concept for concept in concepts if concept.name]


class RegexPhysicsExtractor:
    """Very small deterministic extractor for tests/demos.

    This is not intended to build the final KG from books. It exists so the
    brick can be tested without an LLM/API dependency.
    """

    PATTERNS: tuple[tuple[str, str, list[str]], ...] = (
        (r"newton|seconda legge|second law|f\s*=\s*m\s*a", "Seconda legge di Newton", ["F = m a"]),
        (r"energia cinetica|kinetic energy|1/2\s*m\s*v", "Energia cinetica", ["K = 1/2 m v^2"]),
        (r"quantit[aà] di moto|momentum|p\s*=\s*m\s*v", "Quantità di moto", ["p = m v"]),
        (r"moto armonico|oscillator|pendolo|pendulum", "Oscillazioni", []),
        (r"gravitazione|gravitation|g\s*m\s*m", "Gravitazione", []),
    )

    def extract(self, chunk: SourceChunk) -> list[ExtractedConcept]:
        text = chunk.text.lower()
        found: list[ExtractedConcept] = []
        for pattern, name, formulas in self.PATTERNS:
            if re.search(pattern, text):
                found.append(
                    ExtractedConcept(
                        name=name,
                        description=f"Concept detected from source chunk '{chunk.title}'.",
                        formulas=formulas,
                        bloom_level="understand",
                        confidence=0.4,
                        evidence=chunk.text[:240],
                    )
                )
        return found
