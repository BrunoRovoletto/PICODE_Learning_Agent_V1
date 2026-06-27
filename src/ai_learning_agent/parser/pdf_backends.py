"""Optional PDF-to-Markdown backends.

Best repo mechanism chosen: OpenTutor's Marker -> Markdown parser path.
This module keeps Marker optional so the parser brick remains importable even
without heavy PDF dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
import subprocess


class PdfToMarkdownBackend(Protocol):
    def to_markdown(self, pdf_path: str | Path) -> str:
        """Convert a PDF file to Markdown."""


class MarkerPdfBackend:
    """Marker backend, following OpenTutor's parser choice."""

    _models: dict | None = None

    def _get_models(self) -> dict:
        if self._models is None:
            from marker.models import create_model_dict

            self._models = create_model_dict()
        return self._models

    def to_markdown(self, pdf_path: str | Path) -> str:
        try:
            from marker.converters.pdf import PdfConverter
        except ImportError as exc:
            raise RuntimeError("marker-pdf is not installed. Install `marker-pdf` or use another backend.") from exc
        converter = PdfConverter(artifact_dict=self._get_models())
        rendered = converter(str(pdf_path))
        return rendered.markdown


class PyMuPdf4LlmBackend:
    """Lightweight fallback inspired by Notebook-LM-Mini."""

    def to_markdown(self, pdf_path: str | Path) -> str:
        try:
            from pymupdf4llm import to_markdown
        except ImportError as exc:
            raise RuntimeError("pymupdf4llm is not installed.") from exc
        return to_markdown(str(pdf_path))


class PdfToTextBackend:
    """Dependency-free system fallback using Poppler `pdftotext`.

    This is not the preferred repo mechanism, but it lets us process PDFs in
    this environment when Marker/pymupdf4llm are unavailable.
    """

    def to_markdown(self, pdf_path: str | Path) -> str:
        command = ["pdftotext", "-layout", "-nopgbrk", str(pdf_path), "-"]
        try:
            result = subprocess.run(command, check=True, text=True, capture_output=True)
        except FileNotFoundError as exc:
            raise RuntimeError("pdftotext is not installed.") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"pdftotext failed: {exc.stderr.strip()}") from exc
        return result.stdout


class PlainTextBackend:
    """For tests or already-extracted text/markdown files."""

    def to_markdown(self, pdf_path: str | Path) -> str:
        return Path(pdf_path).read_text(encoding="utf-8")


def get_pdf_backend(name: str) -> PdfToMarkdownBackend:
    if name == "marker":
        return MarkerPdfBackend()
    if name in {"pymupdf4llm", "pymupdf"}:
        return PyMuPdf4LlmBackend()
    if name in {"pdftotext", "poppler"}:
        return PdfToTextBackend()
    if name in {"text", "markdown", "plain"}:
        return PlainTextBackend()
    raise ValueError(f"unknown PDF backend: {name}")
