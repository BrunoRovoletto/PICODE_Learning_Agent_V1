"""OpenTutor-inspired Markdown parser.

Based on OpenTutor's PDF parser ideas:
- PDF/backend converts to Markdown first;
- headings are parsed code-block-aware;
- no-heading documents fall back to paragraph nodes;
- small structural fragments can be merged/thinned.

This implementation is self-contained and outputs parser dataclasses instead of
OpenTutor database models.
"""

from __future__ import annotations

import hashlib
import re

from .models import ParsedSection

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")
CODE_BLOCK_PATTERN = re.compile(r"^```")


def sanitize_title(title: str) -> str:
    title = title.replace("\n", " ").replace("\r", " ")
    title = re.sub(r"\s{2,}", " ", title).strip()
    return title[:120] if title else "Untitled"


def count_tokens(text: str) -> int:
    # Dependency-free approximation: good enough for chunk sizing.
    return max(1, int(len(text.split()) * 0.75)) if text.strip() else 0


def has_headings_code_aware(markdown: str) -> bool:
    in_code_block = False
    for line in markdown.split("\n"):
        stripped = line.strip()
        if CODE_BLOCK_PATTERN.match(stripped):
            in_code_block = not in_code_block
            continue
        if not in_code_block and HEADING_PATTERN.match(line):
            return True
    return False


def parse_markdown_sections(
    markdown: str,
    doc_id: str,
    min_section_tokens: int = 50,
) -> list[ParsedSection]:
    """Parse Markdown into ordered sections."""
    if not markdown.strip():
        return []
    if not has_headings_code_aware(markdown):
        return _sections_from_paragraphs(markdown, doc_id)
    sections = _sections_from_headings(markdown, doc_id)
    return _thin_sections(sections, min_section_tokens=min_section_tokens)


def _section_id(doc_id: str, ordinal: int, title: str) -> str:
    digest = hashlib.sha1(f"{doc_id}:{ordinal}:{title}".encode("utf-8")).hexdigest()[:10]
    return f"section:{doc_id}:{ordinal:05d}:{digest}"


def _sections_from_headings(markdown: str, doc_id: str) -> list[ParsedSection]:
    lines = markdown.splitlines(keepends=True)
    heading_records: list[tuple[int, int, str, int]] = []  # start, level, title, content_start
    in_code_block = False
    char_pos = 0
    for line in lines:
        stripped = line.strip()
        if CODE_BLOCK_PATTERN.match(stripped):
            in_code_block = not in_code_block
        if not in_code_block:
            match = HEADING_PATTERN.match(line.rstrip("\n"))
            if match:
                heading_records.append((char_pos, len(match.group(1)), sanitize_title(match.group(2)), char_pos + len(line)))
        char_pos += len(line)

    if not heading_records:
        return _sections_from_paragraphs(markdown, doc_id)

    sections: list[ParsedSection] = []
    for ordinal, (start, level, title, content_start) in enumerate(heading_records):
        end = heading_records[ordinal + 1][0] if ordinal + 1 < len(heading_records) else len(markdown)
        text = markdown[content_start:end].strip()
        parent_id = _find_parent_id(sections, level)
        section_id = _section_id(doc_id, ordinal, title)
        sections.append(
            ParsedSection(
                section_id=section_id,
                title=title,
                level=level,
                text=text,
                start_char=start,
                end_char=end,
                parent_id=parent_id,
                ordinal=ordinal,
            )
        )
    return sections


def _find_parent_id(sections: list[ParsedSection], level: int) -> str | None:
    for section in reversed(sections):
        if section.level < level:
            return section.section_id
    return None


def _sections_from_paragraphs(markdown: str, doc_id: str, max_tokens: int = 500) -> list[ParsedSection]:
    paragraphs = [(m.start(), m.group(0).strip()) for m in re.finditer(r"(?:^|\n\n)(.*?)(?=\n\n|$)", markdown, flags=re.DOTALL) if m.group(0).strip()]
    sections: list[ParsedSection] = []
    current: list[str] = []
    start_char = 0
    token_count = 0
    ordinal = 0

    for pos, paragraph in paragraphs:
        para_tokens = count_tokens(paragraph)
        if current and token_count + para_tokens > max_tokens:
            text = "\n\n".join(current)
            title = sanitize_title(current[0][:80])
            sections.append(
                ParsedSection(
                    section_id=_section_id(doc_id, ordinal, title),
                    title=title,
                    level=1,
                    text=text,
                    start_char=start_char,
                    end_char=start_char + len(text),
                    ordinal=ordinal,
                )
            )
            ordinal += 1
            current = []
            token_count = 0
        if not current:
            start_char = pos
        current.append(paragraph)
        token_count += para_tokens

    if current:
        text = "\n\n".join(current)
        title = sanitize_title(current[0][:80])
        sections.append(
            ParsedSection(
                section_id=_section_id(doc_id, ordinal, title),
                title=title,
                level=1,
                text=text,
                start_char=start_char,
                end_char=start_char + len(text),
                ordinal=ordinal,
            )
        )
    return sections


def _thin_sections(sections: list[ParsedSection], min_section_tokens: int) -> list[ParsedSection]:
    """Merge tiny sections into previous neighbor.

    This is a lightweight equivalent of OpenTutor's tree thinning. It keeps the
    parser output compact without building a DB tree.
    """
    if len(sections) <= 1:
        return sections
    result: list[ParsedSection] = []
    for section in sections:
        if result and count_tokens(section.text) < min_section_tokens:
            prev = result[-1]
            merged_text = f"{prev.text}\n\n## {section.title}\n{section.text}".strip()
            result[-1] = ParsedSection(
                section_id=prev.section_id,
                title=prev.title,
                level=prev.level,
                text=merged_text,
                start_char=prev.start_char,
                end_char=section.end_char,
                parent_id=prev.parent_id,
                ordinal=prev.ordinal,
                metadata={**prev.metadata, "merged_tiny_sections": [*prev.metadata.get("merged_tiny_sections", []), section.title]},
            )
        else:
            result.append(section)
    return result
