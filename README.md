# AI Learning Agent

Brick-by-brick adaptive learning agent for Physics 1.

This repository is an early experiment built quickly through the Pi coding agent. It agglomerates and reimplements useful concepts from several open-source learning-agent / adaptive-learning repos, with the goal of exploring a local Pi-centered Physics tutor architecture rather than presenting a polished product.

Current planning docs:

- `docs/IMPLEMENTATION_TODO_AGENT_IO_FIRST.md`
- `docs/TEMP_PI_CENTERED_TUTOR_ARCHITECTURE_SPEC.md`
- `docs/agent-io-first-development.odt`

Current bricks:

- `parser`: self-contained Physics book parser with formula-centered chunking.
- `kg`: self-contained knowledge graph construction brick.
- `learner`: Jali-style learner overlay, BKT mastery tracing, ZPD, paths, and reviews.
- `agent_io`: Pi-facing tool/context layer for KG lookup, retrieval, ZPD/path wrappers, learner updates, memory, attempts, exercises, and teaching-context packets.

## Parser brick

Chosen mechanism: **OpenTutor Marker/PDF → Markdown structural parser**, extended with formula-centered Physics chunking.

Pipeline:

```text
PDF/Markdown/Text
  -> Markdown sections
  -> detected formulas
  -> formula-centered chunks
  -> KG-compatible SourceChunk JSONL
```

See:

- `docs/PARSER_BRICK_DECISION.md`
- `src/ai_learning_agent/parser/`

Example:

```bash
PYTHONPATH=src python -m ai_learning_agent.parser.cli parse-markdown \
  --input examples/physics_markdown.md \
  --title "Physics demo" \
  --out /tmp/parsed.json \
  --kg-chunks-out /tmp/kg_chunks.jsonl
```

## Learner brick

Chosen mechanism: **Jali-style learner overlay**, plus OpenTutor-style gap diagnosis.

Pipeline:

```text
Canonical KG JSON
  + LearnerProfile JSON overlay
  -> BKT mastery updates
  -> ZPD recommendations
  -> prerequisite learning paths
  -> mirror learner KG view
```

See:

- `docs/LEARNER_BRICK_DECISION.md`
- `src/ai_learning_agent/learner/`

Example:

```bash
PYTHONPATH=src python -m ai_learning_agent.learner.cli recommend \
  --graph /tmp/kg.json \
  --profile examples/learner_profile.json
```

## KG brick

Chosen mechanism: **OpenTutor LOOM / Graphusion-style KG extraction**, reimplemented cleanly.

Pipeline:

```text
documents JSONL
  -> chunks JSONL
  -> LLM extraction prompts / extraction JSONL
  -> concept fusion
  -> graph JSON
```

See:

- `docs/KG_BRICK_DECISION.md`
- `src/ai_learning_agent/kg/`

## Agent I/O brick

Goal: give Pi stable, compact tool calls while keeping Pi as the flexible tutor-agent.

Architecture invariant:

```text
one canonical teacher KG
+ one LearnerProfile overlay keyed by KnowledgeNode.id
= dynamic learner mirror view, not a second persisted KG
```

Implemented commands:

```text
node
relatives
first-principles
retrieve
zpd
path
exercise-search
exercise-get
record-attempt
attempts
update-learner
memory-get
memory-update
pack-context
```

Examples:

```bash
PYTHONPATH=src python -m ai_learning_agent.agent_io.cli node \
  --graph /tmp/kg.json \
  "Seconda legge di Newton"

PYTHONPATH=src python -m ai_learning_agent.agent_io.cli retrieve \
  --graph /tmp/kg.json \
  --profile examples/learner_profile.json \
  "piano inclinato con attrito"

PYTHONPATH=src python -m ai_learning_agent.agent_io.cli zpd \
  --graph /tmp/kg.json \
  --profile examples/learner_profile.json

PYTHONPATH=src python -m ai_learning_agent.agent_io.cli pack-context \
  --graph /tmp/kg.json \
  --profile examples/learner_profile.json \
  --memory /tmp/learner_memory.json \
  --query "forza risultante" \
  --mode guided_exercise
```

Node metadata is standardized through `KnowledgeNode.properties` rather than by duplicating KG schemas. Useful optional/default fields:

```text
extended_description, difficulty, mastery_threshold, estimated_minutes,
exam_relevance, topic, is_threshold_concept, common_traps,
exercise_ladder_level
```

See:

- `src/ai_learning_agent/agent_io/`
- `tests/test_agent_io_brick.py`

## CLI examples

From this folder:

```bash
python -m ai_learning_agent.kg.cli chunk --docs examples/documents.jsonl --out /tmp/chunks.jsonl
python -m ai_learning_agent.kg.cli prompt --chunks /tmp/chunks.jsonl --out /tmp/prompts.jsonl
python -m ai_learning_agent.kg.cli demo-extract --chunks /tmp/chunks.jsonl --out /tmp/extractions.jsonl
python -m ai_learning_agent.kg.cli fuse --extractions /tmp/extractions.jsonl --out /tmp/fused_extractions.jsonl
python -m ai_learning_agent.kg.cli build --chunks /tmp/chunks.jsonl --extractions /tmp/fused_extractions.jsonl --out /tmp/kg.json
python -m ai_learning_agent.kg.cli summarize --graph /tmp/kg.json
```

The demo extractor is only for smoke tests. Real Mazzoldi/Alonso KG generation should use the prompts with an LLM and then feed extraction JSONL back into the builder.
