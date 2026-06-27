"""Command line interface for the KG brick."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .builder import KnowledgeGraphBuilder
from .chunking import TextChunker
from .extractors import PhysicsPromptBuilder, RegexPhysicsExtractor
from .fusion import ConceptFusion
from .store import (
    read_chunks_jsonl,
    read_documents_jsonl,
    read_extractions_jsonl,
    read_graph_json,
    write_chunks_jsonl,
    write_extractions_jsonl,
    write_graph_json,
)


def cmd_chunk(args: argparse.Namespace) -> None:
    docs = read_documents_jsonl(args.docs)
    chunker = TextChunker(max_chars=args.max_chars, overlap_chars=args.overlap_chars)
    chunks = []
    for doc in docs:
        chunks.extend(chunker.chunk_document(doc))
    write_chunks_jsonl(chunks, args.out)
    print(json.dumps({"documents": len(docs), "chunks": len(chunks), "out": args.out}, ensure_ascii=False))


def cmd_prompt(args: argparse.Namespace) -> None:
    chunks = read_chunks_jsonl(args.chunks)
    builder = PhysicsPromptBuilder()
    with Path(args.out).open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(
                json.dumps(
                    {
                        "chunk_id": chunk.chunk_id,
                        "system": builder.SYSTEM,
                        "prompt": builder.build_user_prompt(chunk),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(json.dumps({"chunks": len(chunks), "out": args.out}, ensure_ascii=False))


def cmd_demo_extract(args: argparse.Namespace) -> None:
    chunks = read_chunks_jsonl(args.chunks)
    extractor = RegexPhysicsExtractor()
    with Path(args.out).open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            concepts = [concept.__dict__ for concept in extractor.extract(chunk)]
            handle.write(json.dumps({"chunk_id": chunk.chunk_id, "concepts": concepts}, ensure_ascii=False) + "\n")
    print(json.dumps({"chunks": len(chunks), "out": args.out, "mode": "regex-demo"}, ensure_ascii=False))


def cmd_fuse(args: argparse.Namespace) -> None:
    extractions = read_extractions_jsonl(args.extractions)
    fusion = ConceptFusion()
    fused_extractions = {}
    total_in = 0
    total_out = 0
    groups_merged = 0
    for chunk_id, concepts in extractions.items():
        result = fusion.fuse(concepts)
        fused_extractions[chunk_id] = result.concepts
        total_in += result.report.input_count
        total_out += result.report.output_count
        groups_merged += result.report.groups_merged
    write_extractions_jsonl(fused_extractions, args.out)
    print(
        json.dumps(
            {
                "in": total_in,
                "out": total_out,
                "groups_merged": groups_merged,
                "method": "lexical_graphusion_style",
                "out_path": args.out,
            },
            ensure_ascii=False,
        )
    )


def cmd_build(args: argparse.Namespace) -> None:
    chunks = {chunk.chunk_id: chunk for chunk in read_chunks_jsonl(args.chunks)}
    extractions = read_extractions_jsonl(args.extractions)
    builder = KnowledgeGraphBuilder()
    missing = []
    for chunk_id, concepts in extractions.items():
        chunk = chunks.get(chunk_id)
        if not chunk:
            missing.append(chunk_id)
            continue
        builder.add_chunk_extraction(chunk, concepts)
    graph = builder.build()
    if missing:
        graph.metadata["missing_chunk_ids"] = missing
    write_graph_json(graph, args.out)
    print(json.dumps({"nodes": len(graph.nodes), "edges": len(graph.edges), "out": args.out}, ensure_ascii=False))


def cmd_summarize(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    by_kind: dict[str, int] = {}
    by_relation: dict[str, int] = {}
    for node in graph.nodes.values():
        by_kind[node.kind] = by_kind.get(node.kind, 0) + 1
    for edge in graph.edges:
        by_relation[edge.relation_type] = by_relation.get(edge.relation_type, 0) + 1
    print(json.dumps({"nodes": len(graph.nodes), "edges": len(graph.edges), "by_kind": by_kind, "by_relation": by_relation}, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Learning Agent KG brick")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("chunk", help="chunk documents JSONL into chunks JSONL")
    p.add_argument("--docs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-chars", type=int, default=3500)
    p.add_argument("--overlap-chars", type=int, default=300)
    p.set_defaults(func=cmd_chunk)

    p = sub.add_parser("prompt", help="write LLM extraction requests for chunks")
    p.add_argument("--chunks", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_prompt)

    p = sub.add_parser("demo-extract", help="deterministic no-LLM demo extraction")
    p.add_argument("--chunks", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_demo_extract)

    p = sub.add_parser("fuse", help="fuse duplicate extracted concepts Graphusion-style")
    p.add_argument("--extractions", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_fuse)

    p = sub.add_parser("build", help="build KG JSON from chunks and extractions")
    p.add_argument("--chunks", required=True)
    p.add_argument("--extractions", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("summarize", help="summarize KG JSON")
    p.add_argument("--graph", required=True)
    p.set_defaults(func=cmd_summarize)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
