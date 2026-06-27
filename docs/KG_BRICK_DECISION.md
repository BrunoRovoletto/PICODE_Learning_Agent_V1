# KG Brick Decision

## Chosen repo mechanism

For the first KG brick we use the **OpenTutor LOOM / Graphusion-style mechanism**.

Repo reference:

- `LearningAgentRepos/OpenTutor/apps/api/services/loom_extraction.py`
- `LearningAgentRepos/OpenTutor/apps/api/services/loom_graph.py`
- `LearningAgentRepos/OpenTutor/apps/api/models/knowledge_graph.py`

## Why this mechanism

The target sources are Physics 1 books, especially:

- Mazzoldi, Nigro, Voci
- Alonso-Finn

For this use case, the graph must capture real educational structure:

- concepts;
- prerequisites;
- related concepts;
- formulas;
- problem families;
- source provenance.

OpenTutor's LOOM extraction is the best fit because its KG mechanism is:

```text
text chunks
  → per-chunk LLM concept extraction
  → prerequisites/related relations
  → Graphusion-style duplicate fusion
  → canonical KnowledgeNode / KnowledgeEdge graph
  → mastery/path queries later
```

## Why not the other repo KG mechanisms

### adaptive-knowledge-graph

Good for storage/RAG and graph visualization, but its KG builder mainly uses:

- YAKE keyword extraction;
- key terms;
- co-occurrence;
- regex prerequisite mining;
- PageRank importance.

That is useful for broad textbook indexing but too shallow for Physics reasoning. It can find terms, but it will not reliably infer that a dynamics exercise requires free-body diagrams, Newton's laws, constraints, and kinematic relations.

### Notebook-LM-Mini

Very good workflow skeleton, but the KG mechanism is smaller and less robust. It is useful for prototype flow, not as the best KG extraction method.

### Jali

Excellent learning-science graph model, but not primarily a book-to-KG extractor.

## Implementation rule for our brick

We re-implement the mechanism in `AI_LEARNING_AGENT` with clean boundaries:

```text
SourceDocument JSONL
  → TextChunker
  → extraction prompts or external extractor
  → ExtractedConcept JSONL
  → ConceptFusion
  → KnowledgeGraphBuilder
  → graph JSON
```

The brick does **not** depend on OpenTutor internals. It preserves the idea and structure, while keeping our code self-contained.

## Current source files

- `src/ai_learning_agent/kg/models.py`
- `src/ai_learning_agent/kg/chunking.py`
- `src/ai_learning_agent/kg/extractors.py`
- `src/ai_learning_agent/kg/fusion.py`
- `src/ai_learning_agent/kg/builder.py`
- `src/ai_learning_agent/kg/store.py`
- `src/ai_learning_agent/kg/cli.py`

## Brick input/output contract

### Input A: documents JSONL

Each line:

```json
{"doc_id":"mazzoldi_vol1","title":"Mazzoldi Nigro Voci Vol. 1","text":"...", "source_path":"..."}
```

### Output A: chunks JSONL

Each line:

```json
{"chunk_id":"...", "doc_id":"...", "title":"...", "text":"...", "ordinal":0}
```

### Input B: extractions JSONL

Each line:

```json
{"chunk_id":"...", "concepts":[{"name":"Seconda legge di Newton", "prerequisites":["Vettori"], "formulas":["F = ma"]}]}
```

### Output B: KG JSON

```json
{
  "metadata": {...},
  "nodes": [...],
  "edges": [...]
}
```
