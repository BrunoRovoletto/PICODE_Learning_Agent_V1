# Temporary Spec: Pi-Centered Physics Tutor Architecture

Status: temporary brainstorming/specification document.

## Core philosophy

Pi should remain the central teaching agent.

The system should not hardcode a full tutor brain. Instead, it should provide Pi
with reliable tools, retrieval, structured memory, deterministic learning rails,
and compact context packets.

```text
KG + learner overlay + exercises + retrieval + deterministic updates
  -> compact context packet
  -> Pi tutor-agent reasons and teaches
  -> structured assessment/update JSON
  -> deterministic state update
```

## Current bricks

Already implemented:

1. `parser` brick
   - PDF/Markdown/Text -> formula-centered chunks.

2. `kg` brick
   - chunks + extractions -> canonical teacher knowledge graph.

3. `learner` brick
   - Jali-style learner overlay keyed by KG node id.
   - BKT mastery update.
   - ZPD recommendation.
   - prerequisite learning paths.
   - spaced-repetition-ready timestamps and review state.

## Important KG architecture note

There is **one canonical teacher KG**.

The learner does **not** get a duplicated KG.

Instead:

```text
Canonical Physics KG
  + LearnerProfile overlay keyed by KnowledgeNode.id
  = dynamic mirror learner KG view
```

So conceptually the UI may show a "learner KG", but physically the architecture
has:

1. one KG: the canonical Physics/teacher KG;
2. one learner overlay: user-specific state per KG node.

This avoids duplicate graph drift while still enabling a personal mirror view.

## Commands/tools Pi should have

### KG/content commands

```text
kg.search(query, kinds?, limit?)
kg.node(node_id, include_neighbors?, include_sources?, include_user_state?)
kg.neighborhood(node_id, depth?, relation_types?)
kg.sources(node_id, limit?)
```

Purpose: retrieve canonical content, formulas, prerequisites, related concepts,
and source-grounded quotes.

### Learner-state commands

```text
learner.state(node_ids?)
learner.zpd(max_results?, mode?)
learner.path(target_node_id, max_paths?)
learner.update(assessment_json)
learner.mirror(limit?)
```

Purpose: inspect and update the learner overlay.

### Exercise commands

Not yet implemented, but needed:

```text
exercise.search(concepts?, difficulty?, max_new_concepts?, source_priority?, limit?)
exercise.get(exercise_id)
exercise.record_attempt(attempt_json)
```

Purpose: let Pi choose and guide real Physics 1 exercises.

### Informal memory commands

Not yet implemented, but useful:

```text
memory.get()
memory.update(summary_json)
```

Purpose: store learning style, burnout/focus state, recurring difficulties, and
session-level notes separate from formal KG mastery.

### Context-packing command

Highly recommended:

```text
context.pack(mode, exercise_id?, target_node_id?, max_tokens?)
```

Purpose: give Pi the right small slice of context for one teaching call.

## ZPD definition

Simple deterministic definition:

A node is in the learner's ZPD if:

```text
1. The node is not mastered.
2. All direct prerequisites are mastered.
3. The node difficulty is not too far above learner ability.
```

Where:

```text
mastered(node) = learner.mastery[node] >= node.mastery_threshold
ability = weighted average of attempted node mastery
ready if node.difficulty <= ability + tolerance
```

Suggested command:

```text
learner.zpd(max_results=10, mode="exam_sprint")
```

Suggested output:

```json
{
  "ability": 0.42,
  "ready": [
    {
      "node_id": "newton2",
      "label": "Seconda legge di Newton",
      "mastery": 0.35,
      "difficulty": 0.50,
      "reason": "prerequisites mastered, high exam relevance"
    }
  ],
  "blocked": [
    {
      "node_id": "inclined_plane",
      "label": "Piano inclinato",
      "blocked_by": ["Seconda legge di Newton"]
    }
  ]
}
```

## Bayesian mastery update

Keep this close to Jali/OpenTutor BKT.

Pi should not directly set mastery. Pi should produce an assessment packet based
on the user's attempt.

Input from Pi:

```json
{
  "exercise_id": "ex_123",
  "node_evaluations": [
    {
      "node_id": "free_body_diagram",
      "correct": false,
      "confidence": 0.85,
      "mistake": "forgot normal force",
      "question_type": "free_response",
      "quality": 2
    },
    {
      "node_id": "newton2",
      "correct": true,
      "confidence": 0.75,
      "quality": 4
    }
  ]
}
```

Deterministic function:

```text
learner.update(assessment_json)
```

Output:

```json
{
  "updates": [
    {
      "node_id": "free_body_diagram",
      "previous_mastery": 0.42,
      "new_mastery": 0.21,
      "gap_type": "fundamental_gap",
      "next_review_at": "2026-06-28T10:00:00+00:00"
    }
  ]
}
```

Separation of responsibility:

```text
Pi evaluates the attempt and emits structured evidence.
BKT updates mastery deterministically.
```

## Learning path

Deterministic path function:

```text
target node
  -> collect transitive prerequisites
  -> remove mastered nodes
  -> topologically sort
  -> return compact path(s)
```

Suggested command:

```text
learner.path(target_node_id="inclined_plane", max_paths=3)
```

Output:

```json
{
  "target": "Piano inclinato",
  "paths": [
    {
      "steps": [
        {"node_id": "vectors", "label": "Componenti vettoriali", "mastery": 0.45},
        {"node_id": "free_body", "label": "Diagramma delle forze", "mastery": 0.25},
        {"node_id": "newton2", "label": "Seconda legge di Newton", "mastery": 0.35},
        {"node_id": "inclined_plane", "label": "Piano inclinato", "mastery": 0.0}
      ]
    }
  ]
}
```

Pi can reason over this path and choose a smaller or gentler subset for the
current session.

## Spaced repetition data

Every learner node update should deterministically record system-generated UTC
timestamps:

```json
{
  "last_attempt_at": "2026-06-27T12:00:00+00:00",
  "attempts": 5,
  "streak": 2,
  "quality": 4,
  "next_review_at": "2026-06-29T12:00:00+00:00"
}
```

Recommended future addition:

```text
attempts.jsonl
```

An append-only attempt log makes spaced repetition and mastery recomputation
possible later.

## Skill metadata

Store skill metadata in `KnowledgeNode.properties`.

Example:

```json
{
  "difficulty": 0.55,
  "mastery_threshold": 0.8,
  "estimated_minutes": 15,
  "exam_relevance": 0.9,
  "bloom_level": "apply",
  "is_threshold_concept": true,
  "topic": "Dinamica"
}
```

Metadata may be:

1. extracted by LLM during KG construction;
2. added/edited by Pi;
3. defaulted deterministically when missing.

## Informal user memory

Keep this separate from formal KG mastery.

Suggested file:

```text
learner_memory.json
```

Shape:

```json
{
  "learning_style": {
    "prefers": ["visual intuition first", "short steps"],
    "avoid": ["long derivations before examples"]
  },
  "current_constraints": {
    "exam_days_left": 7,
    "burnout_level": "high",
    "focus_span_minutes": 20
  },
  "recurring_difficulties": [
    "free-body diagrams",
    "sign conventions",
    "knowing which formula to choose"
  ],
  "recent_notes": [
    "gets overwhelmed by multi-concept problems"
  ]
}
```

Pi can update this after sessions using `memory.update(summary_json)`.

## Gradual exercise progression

Exercise records should eventually include:

```text
required_concepts
problem_type
difficulty
number_of_steps
algebra_load
has_trap
source
solution_available
```

Deterministic exercise search should prefer:

```text
prerequisites mostly mastered
only 0-1 weak/new concept
difficulty near current ability
course/exam source priority
```

Progression ladder:

```text
1. recognition question
2. one-formula direct exercise
3. same concept with numbers changed
4. two-step problem
5. mixed-concept problem
6. exam-style problem
7. trap/edge-case problem
```

Pi handles explanation and emotional adaptation, while deterministic filtering
keeps the difficulty sane.

## Context packing for Pi calls

Pi should not receive the whole KG. It should receive a compact packet.

Suggested command:

```text
context.pack(mode="guided_exercise", exercise_id="ex_123")
```

Suggested packet:

```json
{
  "mode": "guided_exercise",
  "exercise": {
    "id": "ex_123",
    "statement": "..."
  },
  "relevant_nodes": [
    {
      "node_id": "newton2",
      "label": "Seconda legge di Newton",
      "formula": "F = ma",
      "mastery": 0.35,
      "gap_type": "transfer_gap"
    }
  ],
  "zpd_snapshot": {},
  "recent_mistakes": ["forgot normal force"],
  "user_preferences": ["visual first", "short steps"],
  "source_quotes": ["..."],
  "allowed_actions": [
    "ask_question",
    "give_hint",
    "evaluate_attempt",
    "request_more_context",
    "update_memory"
  ]
}
```

Pi response should ideally contain:

1. natural language message to the user;
2. optional structured action/update JSON.

Example action:

```json
{
  "action": "evaluate_attempt",
  "assessment": {
    "node_evaluations": [
      {
        "node_id": "free_body_diagram",
        "correct": false,
        "mistake": "missing friction direction",
        "quality": 2
      }
    ]
  }
}
```

## Recommended next brick

Next useful brick should probably be one of:

1. **Pi tool/context layer**
   - expose KG search, learner.zpd, learner.path, learner.update, context.pack.

2. **Exercise indexing brick**
   - parse/record exercises and connect them to KG nodes.

Best immediate path:

```text
minimal exercise indexing + context.pack + Pi-facing commands
```

This keeps Pi central while giving it deterministic, reliable learning tools.
