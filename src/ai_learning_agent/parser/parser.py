"""High-level parser brick orchestration."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .chunking import FormulaCenteredChunker
from .formulas import detect_formulas
from .markdown import parse_markdown_sections
from .models import ParsedDocument
from .pdf_backends import PdfToMarkdownBackend, get_pdf_backend


def stable_doc_id(title_or_path: str) -> str:
    stem = Path(title_or_path).stem.lower().replace(" ", "_")[:40] or "document"
    digest = hashlib.sha1(title_or_path.encode("utf-8")).hexdigest()[:8]
    return f"{stem}_{digest}"


class PhysicsDocumentParser:
    """Parse Physics PDF/Markdown into formula-centered chunks.

    Mechanism:
    - OpenTutor-style PDF/Markdown structural parsing;
    - formula detection;
    - formula-centered chunking;
    - sequential links for later RAG/KG navigation.
    """

    def __init__(
        self,
        pdf_backend: PdfToMarkdownBackend | None = None,
        chunker: FormulaCenteredChunker | None = None,
    ) -> None:
        self.pdf_backend = pdf_backend
        self.chunker = chunker or FormulaCenteredChunker()

    @classmethod
    def from_backend_name(cls, backend_name: str = "marker") -> "PhysicsDocumentParser":
        return cls(pdf_backend=get_pdf_backend(backend_name))

    def parse_markdown(
        self,
        markdown: str,
        title: str,
        doc_id: str | None = None,
        source_path: str | None = None,
    ) -> ParsedDocument:
        doc_id = doc_id or stable_doc_id(title)
        sections = parse_markdown_sections(markdown, doc_id=doc_id)
        formulas = detect_formulas(markdown, doc_id=doc_id)
        chunks = self.chunker.chunk(
            doc_id=doc_id,
            title=title,
            markdown=markdown,
            sections=sections,
            formulas=formulas,
            source_path=source_path,
        )
        return ParsedDocument(
            doc_id=doc_id,
            title=title,
            markdown=markdown,
            source_path=source_path,
            sections=sections,
            formulas=formulas,
            chunks=chunks,
            metadata={
                "parser": "PhysicsDocumentParser",
                "mechanism": "opentutor_marker_markdown_plus_formula_centered_chunking",
                "section_count": len(sections),
                "formula_count": len(formulas),
                "chunk_count": len(chunks),
            },
        )

    def parse_file(
        self,
        path: str | Path,
        title: str | None = None,
        doc_id: str | None = None,
        backend_name: str | None = None,
    ) -> ParsedDocument:
        path = Path(path)
        title = title or path.stem
        backend = self.pdf_backend
        if backend_name:
            backend = get_pdf_backend(backend_name)
        if path.suffix.lower() in {".md", ".markdown", ".txt"}:
            markdown = path.read_text(encoding="utf-8")
        else:
            if backend is None:
                backend = get_pdf_backend("marker")
            markdown = backend.to_markdown(path)
        return self.parse_markdown(markdown, title=title, doc_id=doc_id, source_path=str(path))
