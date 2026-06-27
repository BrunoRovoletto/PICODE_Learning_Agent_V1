"""CLI for parser brick."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .parser import PhysicsDocumentParser
from .store import write_kg_chunks_jsonl, write_parsed_document, write_parser_chunks_jsonl


def cmd_parse(args: argparse.Namespace) -> None:
    parser = PhysicsDocumentParser.from_backend_name(args.backend)
    document = parser.parse_file(args.input, title=args.title, doc_id=args.doc_id, backend_name=args.backend)
    if args.out:
        write_parsed_document(document, args.out)
    if args.chunks_out:
        write_parser_chunks_jsonl(document.chunks, args.chunks_out)
    if args.kg_chunks_out:
        write_kg_chunks_jsonl(document.chunks, args.kg_chunks_out)
    print(
        json.dumps(
            {
                "doc_id": document.doc_id,
                "title": document.title,
                "sections": len(document.sections),
                "formulas": len(document.formulas),
                "chunks": len(document.chunks),
                "out": args.out,
                "chunks_out": args.chunks_out,
                "kg_chunks_out": args.kg_chunks_out,
            },
            ensure_ascii=False,
        )
    )


def cmd_parse_markdown(args: argparse.Namespace) -> None:
    markdown = Path(args.input).read_text(encoding="utf-8")
    parser = PhysicsDocumentParser()
    document = parser.parse_markdown(markdown, title=args.title or Path(args.input).stem, doc_id=args.doc_id, source_path=args.input)
    if args.out:
        write_parsed_document(document, args.out)
    if args.chunks_out:
        write_parser_chunks_jsonl(document.chunks, args.chunks_out)
    if args.kg_chunks_out:
        write_kg_chunks_jsonl(document.chunks, args.kg_chunks_out)
    print(
        json.dumps(
            {
                "doc_id": document.doc_id,
                "sections": len(document.sections),
                "formulas": len(document.formulas),
                "chunks": len(document.chunks),
                "out": args.out,
                "chunks_out": args.chunks_out,
                "kg_chunks_out": args.kg_chunks_out,
            },
            ensure_ascii=False,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Learning Agent parser brick")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("parse", help="parse PDF/markdown/text into formula-centered chunks")
    p.add_argument("--input", required=True)
    p.add_argument("--title")
    p.add_argument("--doc-id")
    p.add_argument("--backend", default="marker", choices=["marker", "pymupdf4llm", "pymupdf", "pdftotext", "poppler", "text", "markdown", "plain"])
    p.add_argument("--out")
    p.add_argument("--chunks-out")
    p.add_argument("--kg-chunks-out")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("parse-markdown", help="parse already extracted markdown/text")
    p.add_argument("--input", required=True)
    p.add_argument("--title")
    p.add_argument("--doc-id")
    p.add_argument("--out")
    p.add_argument("--chunks-out")
    p.add_argument("--kg-chunks-out")
    p.set_defaults(func=cmd_parse_markdown)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
