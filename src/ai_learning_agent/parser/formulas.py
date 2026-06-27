"""Formula detection for Physics parser chunks.

The repos had generic parsers/chunkers, but not formula-centered chunking.
This module adds the Physics-specific layer while keeping OpenTutor's
Markdown-first parser approach.
"""

from __future__ import annotations

import hashlib
import re

from .models import ParsedFormula

# Common Markdown/LaTeX math containers.
DISPLAY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("display_math", re.compile(r"\$\$(.+?)\$\$", re.DOTALL)),
    ("display_math", re.compile(r"\\\[(.+?)\\\]", re.DOTALL)),
    ("equation_env", re.compile(r"\\begin\{(?:equation|align|gather|multline)\*?\}(.+?)\\end\{(?:equation|align|gather|multline)\*?\}", re.DOTALL)),
)

INLINE_MATH_PATTERN = re.compile(r"(?<!\$)\$(?!\$)(.{3,120}?)(?<!\$)\$(?!\$)", re.DOTALL)

# Heuristic for OCR/Markdown lines that contain equations but no LaTeX delimiters.
FORMULA_LINE_PATTERN = re.compile(
    r"(?im)^\s*(?:[A-Za-zΑ-ωàèéìòùÀÈÉÌÒÙ][\wΑ-ωàèéìòùÀÈÉÌÒÙ_()\s,.'-]{0,80})?"
    r"(?:=|≈|≃|≤|≥|\+\s*C|\bproporzionale\b|\bproportional\b)"
    r"[^\n]{2,160}$"
)


def _formula_id(doc_id: str, start: int, text: str) -> str:
    digest = hashlib.sha1(f"{doc_id}:{start}:{text}".encode("utf-8")).hexdigest()[:12]
    return f"formula:{doc_id}:{digest}"


def _clean_formula(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip("` ")


def detect_formulas(markdown: str, doc_id: str) -> list[ParsedFormula]:
    """Detect formulas in Markdown/text while preserving source positions."""
    formulas: list[ParsedFormula] = []
    occupied: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(start < b and end > a for a, b in occupied)

    for kind, pattern in DISPLAY_PATTERNS:
        for match in pattern.finditer(markdown):
            text = _clean_formula(match.group(1))
            if not text:
                continue
            formulas.append(
                ParsedFormula(
                    formula_id=_formula_id(doc_id, match.start(), text),
                    text=text,
                    kind=kind,  # type: ignore[arg-type]
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )
            occupied.append((match.start(), match.end()))

    for match in INLINE_MATH_PATTERN.finditer(markdown):
        if overlaps(match.start(), match.end()):
            continue
        text = _clean_formula(match.group(1))
        if _looks_formulaic(text):
            formulas.append(
                ParsedFormula(
                    formula_id=_formula_id(doc_id, match.start(), text),
                    text=text,
                    kind="inline_math",
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )
            occupied.append((match.start(), match.end()))

    for match in FORMULA_LINE_PATTERN.finditer(markdown):
        if overlaps(match.start(), match.end()):
            continue
        text = _clean_formula(match.group(0))
        if _looks_formulaic(text):
            formulas.append(
                ParsedFormula(
                    formula_id=_formula_id(doc_id, match.start(), text),
                    text=text,
                    kind="formula_line",
                    start_char=match.start(),
                    end_char=match.end(),
                )
            )
            occupied.append((match.start(), match.end()))

    formulas.sort(key=lambda f: f.start_char)
    return _dedupe_near_duplicates(formulas)


def _looks_formulaic(text: str) -> bool:
    if len(text) < 3:
        return False
    has_operator = bool(re.search(r"=|≈|≃|≤|≥|\+|-|/|\^|_", text))
    has_symbol = bool(re.search(r"[A-Za-zΑ-ω]", text))
    has_physics_pattern = bool(re.search(r"\b(sin|cos|tan|sqrt|frac|Delta|omega|alpha|theta|vec|dot)\b|\\", text))
    return has_operator and (has_symbol or has_physics_pattern)


def _dedupe_near_duplicates(formulas: list[ParsedFormula]) -> list[ParsedFormula]:
    seen: set[str] = set()
    result: list[ParsedFormula] = []
    for formula in formulas:
        key = re.sub(r"\s+", "", formula.text.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(formula)
    return result
