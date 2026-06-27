# Learner Brick Decision

## Chosen mechanism

The learner brick uses **Jali's learner overlay architecture**:

```text
Canonical teacher KG + per-node learner state = dynamic mirror learner KG
```

It does not duplicate the KG. The canonical Physics KG remains the source of
truth for concepts, formulas, problem types, prerequisites, source evidence, and
metadata. Learner state is stored separately and keyed by `KnowledgeNode.id`.

## Repo ideas reused

### Jali

Files:

- `packages/core/src/types/mastery.ts`
- `packages/core/src/assessment/bkt.ts`
- `packages/core/src/query/zpd.ts`
- `packages/core/src/query/path.ts`
- `packages/core/src/query/spaced-repetition.ts`

Reused ideas:

- `MasteryState` per skill/node.
- Bayesian Knowledge Tracing.
- ZPD: ready if prerequisites are mastered and difficulty is near ability.
- Prerequisite-aware learning paths.
- SM-2-style review scheduling.

### OpenTutor

Files:

- `apps/api/models/progress.py`
- `apps/api/services/learning_science/difficulty_selector.py`
- `apps/api/services/learning_science/knowledge_tracer.py`

Reused ideas:

- `gap_type`: `fundamental_gap`, `transfer_gap`, `trap_vulnerability`, `mastered`.
- Difficulty bands from mastery: low -> fundamentals, mid -> application, high -> traps.

### adaptive-knowledge-graph / Notebook-LM-Mini

Reused only the simple JSON persistence/MVP spirit, not their full service code.

## Compatibility with current KG

Jali's `SkillNode` maps cleanly to our `KnowledgeNode`:

```text
SkillNode.id             -> KnowledgeNode.id
SkillNode.name           -> KnowledgeNode.label
SkillNode.difficulty     -> KnowledgeNode.properties["difficulty"]
SkillNode.masteryThreshold -> KnowledgeNode.properties["mastery_threshold"]
Skill prerequisites      -> KnowledgeEdge(relation_type="REQUIRES")
```

Current trackable node kinds:

- `concept`
- `formula`
- `problem_type`

We intentionally ignore `source_chunk` for learner mastery.

## CLI examples

Update after one answer:

```bash
PYTHONPATH=src python -m ai_learning_agent.learner.cli update \
  --profile /tmp/learner.json \
  --node-id concept:forza-risultante \
  --correct \
  --quality 4
```

Recommend next nodes:

```bash
PYTHONPATH=src python -m ai_learning_agent.learner.cli recommend \
  --graph /tmp/kg.json \
  --profile /tmp/learner.json
```

Render the mirror learner KG view:

```bash
PYTHONPATH=src python -m ai_learning_agent.learner.cli mirror \
  --graph /tmp/kg.json \
  --profile /tmp/learner.json
```
