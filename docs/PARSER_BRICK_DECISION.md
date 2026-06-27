# Parser Brick Decision

## Chosen repo mechanism

The parser brick uses **OpenTutor's PDF parser mechanism** as the base.

Repo reference:

- `LearningAgentRepos/OpenTutor/apps/api/services/parser/pdf.py`

Key ideas reused:

- PDF is converted to Markdown first.
- Markdown headings are parsed code-block-aware.
- No-heading documents fall back to paragraph splitting.
- Tiny sections are merged/thinned to avoid useless fragments.

## Why OpenTutor is the best parser base

For Mazzoldi and Alonso-Finn, we need robust book parsing before KG extraction.
OpenTutor's parser is better than the other repos because it is designed for
PDF → structured course tree.

Comparison:

- `Notebook-LM-Mini`: useful and simple `pymupdf4llm -> markdown -> ## split`, but too shallow.
- `adaptive-knowledge-graph`: good sequential RAG chunker, but not a PDF parser.
- `Jali`: parser abstractions, but not a book/PDF parser.
- `OpenTutor`: strongest Markdown/PDF structure parser.

## Physics-specific extension

None of the repos has true formula-centered chunking.

So our brick extends OpenTutor's mechanism with:

```text
PDF/Markdown
  -> Markdown sections
  -> formula detection
  -> formula-centered context chunks
  -> sequential chunk links
  -> KG-compatible SourceChunk JSONL
```

## Output contract

The parser can write:

1. full parsed document JSON;
2. parser-native chunks JSONL;
3. KG-compatible `SourceChunk` JSONL.

This means the parser brick can feed the KG brick without tight coupling.

## CLI examples

Parse an already extracted Markdown/text file:

```bash
PYTHONPATH=src python -m ai_learning_agent.parser.cli parse-markdown \
  --input example.md \
  --title "Mazzoldi demo" \
  --kg-chunks-out /tmp/kg_chunks.jsonl
```

Parse a PDF using OpenTutor-style Marker backend:

```bash
PYTHONPATH=src python -m ai_learning_agent.parser.cli parse \
  --input book.pdf \
  --backend marker \
  --kg-chunks-out /tmp/kg_chunks.jsonl
```

If Marker is unavailable, the CLI also supports the Notebook-LM-Mini fallback:

```bash
PYTHONPATH=src python -m ai_learning_agent.parser.cli parse \
  --input book.pdf \
  --backend pymupdf4llm \
  --kg-chunks-out /tmp/kg_chunks.jsonl
```

In this environment, Marker/pymupdf4llm may not be installed. A practical
system fallback is also available:

```bash
PYTHONPATH=src python -m ai_learning_agent.parser.cli parse \
  --input book.pdf \
  --backend pdftotext \
  --kg-chunks-out /tmp/kg_chunks.jsonl
```
