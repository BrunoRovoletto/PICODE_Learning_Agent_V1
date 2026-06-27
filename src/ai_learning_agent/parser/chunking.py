"""Formula-centered chunking for Physics books."""

from __future__ import annotations

import hashlib
import re

from .models import ParsedFormula, ParsedSection, ParserChunk


def _chunk_id(doc_id: str, ordinal: int, text: str) -> str:
    digest = hashlib.sha1(f"{doc_id}:{ordinal}:{text[:200]}".encode("utf-8")).hexdigest()[:12]
    return f"pchunk:{doc_id}:{ordinal:05d}:{digest}"


class FormulaCenteredChunker:
    """Create chunks around formulas, with sequential links.

    Strategy:
    - If a section has formulas, each formula gets a local context window.
    - Remaining text becomes paragraph/section chunks.
    - If a section has no formulas, use paragraph-aware section chunks.

    This is the Physics-specific improvement missing from the repos.
    """

    def __init__(
        self,
        context_chars_before: int = 900,
        context_chars_after: int = 900,
        max_chunk_chars: int = 2600,
        min_chunk_chars: int = 180,
    ) -> None:
        self.context_chars_before = context_chars_before
        self.context_chars_after = context_chars_after
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars

    def chunk(
        self,
        doc_id: str,
        title: str,
        markdown: str,
        sections: list[ParsedSection],
        formulas: list[ParsedFormula],
        source_path: str | None = None,
    ) -> list[ParserChunk]:
        chunks: list[ParserChunk] = []
        ordinal = 0
        formulas_by_section = self._assign_formulas_to_sections(sections, formulas)

        for section in sections:
            section_formulas = formulas_by_section.get(section.section_id, [])
            if section_formulas:
                for formula in section_formulas:
                    text, start, end = self._formula_context(markdown, formula)
                    chunks.append(
                        ParserChunk(
                            chunk_id=_chunk_id(doc_id, ordinal, text),
                            doc_id=doc_id,
                            title=f"{title} — {section.title}",
                            text=text,
                            ordinal=ordinal,
                            kind="formula_context",
                            source_path=source_path,
                            section_id=section.section_id,
                            formula_ids=[formula.formula_id],
                            start_char=start,
                            end_char=end,
                            metadata={"formula_text": formula.text, "formula_kind": formula.kind},
                        )
                    )
                    ordinal += 1

                # Add a compact non-formula section context if useful.
                stripped = self._remove_formula_spans(section.text, section_formulas, section.start_char)
                if len(stripped.strip()) >= self.min_chunk_chars:
                    for text in self._paragraph_chunks(stripped):
                        chunks.append(
                            ParserChunk(
                                chunk_id=_chunk_id(doc_id, ordinal, text),
                                doc_id=doc_id,
                                title=f"{title} — {section.title}",
                                text=text,
                                ordinal=ordinal,
                                kind="section",
                                source_path=source_path,
                                section_id=section.section_id,
                                start_char=section.start_char,
                                end_char=section.end_char,
                            )
                        )
                        ordinal += 1
            else:
                for text in self._paragraph_chunks(section.text):
                    chunks.append(
                        ParserChunk(
                            chunk_id=_chunk_id(doc_id, ordinal, text),
                            doc_id=doc_id,
                            title=f"{title} — {section.title}",
                            text=text,
                            ordinal=ordinal,
                            kind="paragraph" if len(text) < self.max_chunk_chars else "section",
                            source_path=source_path,
                            section_id=section.section_id,
                            start_char=section.start_char,
                            end_char=section.end_char,
                        )
                    )
                    ordinal += 1

        self._link_sequential(chunks)
        return chunks

    def _assign_formulas_to_sections(
        self,
        sections: list[ParsedSection],
        formulas: list[ParsedFormula],
    ) -> dict[str, list[ParsedFormula]]:
        result: dict[str, list[ParsedFormula]] = {section.section_id: [] for section in sections}
        for formula in formulas:
            containing = [s for s in sections if s.start_char <= formula.start_char <= s.end_char]
            if containing:
                # Pick deepest/latest matching section.
                section = max(containing, key=lambda s: (s.level, s.start_char))
            elif sections:
                section = min(sections, key=lambda s: abs(s.start_char - formula.start_char))
            else:
                continue
            result.setdefault(section.section_id, []).append(formula)
        return result

    def _formula_context(self, markdown: str, formula: ParsedFormula) -> tuple[str, int, int]:
        start = max(0, formula.start_char - self.context_chars_before)
        end = min(len(markdown), formula.end_char + self.context_chars_after)
        start = self._move_to_boundary(markdown, start, direction="left")
        end = self._move_to_boundary(markdown, end, direction="right")
        text = markdown[start:end].strip()
        if len(text) > self.max_chunk_chars:
            formula_center = formula.start_char - start
            half = self.max_chunk_chars // 2
            local_start = max(0, formula_center - half)
            local_end = min(len(text), local_start + self.max_chunk_chars)
            text = text[local_start:local_end].strip()
            start += local_start
            end = start + len(text)
        return text, start, end

    @staticmethod
    def _move_to_boundary(text: str, pos: int, direction: str) -> int:
        if direction == "left":
            candidates = [text.rfind("\n\n", 0, pos), text.rfind(". ", 0, pos)]
            best = max(candidates)
            return best + 2 if best >= 0 else pos
        candidates = [text.find("\n\n", pos), text.find(". ", pos)]
        candidates = [c for c in candidates if c >= 0]
        return (min(candidates) + 2) if candidates else pos

    def _paragraph_chunks(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs or [text.strip()]:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= self.max_chunk_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = paragraph
        if current and len(current) >= self.min_chunk_chars:
            chunks.append(current)
        elif current and not chunks:
            chunks.append(current)
        return chunks

    @staticmethod
    def _remove_formula_spans(section_text: str, formulas: list[ParsedFormula], section_start: int) -> str:
        spans = sorted((max(0, f.start_char - section_start), max(0, f.end_char - section_start)) for f in formulas)
        result_parts: list[str] = []
        cursor = 0
        for start, end in spans:
            result_parts.append(section_text[cursor:start])
            cursor = max(cursor, end)
        result_parts.append(section_text[cursor:])
        return "\n\n".join(part.strip() for part in result_parts if part.strip())

    @staticmethod
    def _link_sequential(chunks: list[ParserChunk]) -> None:
        # ParserChunk is frozen, so replace entries in list with linked copies.
        from dataclasses import replace

        for i, chunk in enumerate(list(chunks)):
            chunks[i] = replace(
                chunk,
                previous_chunk_id=chunks[i - 1].chunk_id if i > 0 else None,
                next_chunk_id=chunks[i + 1].chunk_id if i + 1 < len(chunks) else None,
            )
