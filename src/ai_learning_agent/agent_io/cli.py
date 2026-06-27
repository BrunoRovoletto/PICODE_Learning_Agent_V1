"""CLI wrappers for the agent I/O brick.

These commands are intentionally simple so Pi can call them through shell now,
and they can later be wrapped as first-class Pi tools.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_learning_agent.kg.models import KnowledgeGraph
from ai_learning_agent.kg.store import read_graph_json
from ai_learning_agent.learner.models import LearnerProfile
from ai_learning_agent.learner.store import read_profile_json, write_profile_json

from .attempts import read_attempts, record_attempt
from .context import pack_teaching_context
from .exercises import get_exercise, read_exercises_jsonl, search_exercises
from .kg_queries import get_from_first_principles, get_node, get_node_relatives
from .learner_tools import get_learning_path, get_proximal_dev, update_learner
from .memory import get_user_memory, update_user_memory
from .retrieval import context_retrieve


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _load_graph(path: str | None) -> KnowledgeGraph | None:
    return read_graph_json(path) if path else None


def _load_profile(path: str | None) -> LearnerProfile | None:
    return read_profile_json(path) if path else None


def _read_json_arg(value: str | None, file_path: str | None) -> dict[str, Any]:
    if file_path:
        return json.loads(Path(file_path).read_text(encoding="utf-8"))
    if value:
        return json.loads(value)
    return {}


def _csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def cmd_node(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = _load_profile(args.profile)
    _print_json(
        get_node(
            graph,
            args.query,
            profile=profile,
            fields=_csv(args.fields),
            include_relatives=args.include_relatives,
            include_sources=not args.no_sources,
            include_user_state=not args.no_user_state,
        )
    )


def cmd_relatives(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = _load_profile(args.profile)
    _print_json(
        get_node_relatives(
            graph,
            args.node,
            profile=profile,
            depth=args.depth,
            direction=args.direction,
            relation_types=_csv(args.relation_types),
            unpack=args.unpack,
        )
    )


def cmd_first_principles(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = _load_profile(args.profile)
    _print_json(get_from_first_principles(graph, args.node, profile=profile, max_paths=args.max_paths, pruned=not args.no_prune))


def cmd_retrieve(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = _load_profile(args.profile)
    _print_json(context_retrieve(graph, args.query, profile=profile, intent=args.intent, limit=args.limit))


def cmd_zpd(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = read_profile_json(args.profile) if args.profile else LearnerProfile()
    _print_json(get_proximal_dev(graph, profile, max_results=args.max_results, mode=args.mode))


def cmd_path(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = read_profile_json(args.profile) if args.profile else LearnerProfile()
    _print_json(
        get_learning_path(
            graph,
            profile,
            goal_node=args.goal_node,
            mode=args.mode,
            max_steps=args.max_steps,
            session_minutes=args.session_minutes,
        )
    )


def cmd_exercise_search(args: argparse.Namespace) -> None:
    exercises = read_exercises_jsonl(args.exercises)
    graph = _load_graph(args.graph)
    profile = _load_profile(args.profile)
    _print_json(
        {
            "results": search_exercises(
                exercises,
                query=args.query,
                target_nodes=args.target_node or [],
                graph=graph,
                profile=profile,
                difficulty=args.difficulty,
                max_new_concepts=args.max_new_concepts,
                source_priority=args.source_priority,
                ladder_level=args.ladder_level,
                limit=args.limit,
            )
        }
    )


def cmd_exercise_get(args: argparse.Namespace) -> None:
    exercises = read_exercises_jsonl(args.exercises)
    graph = _load_graph(args.graph)
    profile = _load_profile(args.profile)
    _print_json(get_exercise(exercises, args.exercise_id, graph=graph, profile=profile, include_solution=args.include_solution))


def cmd_record_attempt(args: argparse.Namespace) -> None:
    attempt = _read_json_arg(args.json, args.json_file)
    _print_json(record_attempt(args.attempts, attempt))


def cmd_update_learner(args: argparse.Namespace) -> None:
    graph = _load_graph(args.graph)
    profile = read_profile_json(args.profile) if args.profile else LearnerProfile()
    assessment = _read_json_arg(args.json, args.json_file)
    updated, packet = update_learner(graph, profile, assessment, mode=args.mode)
    out = args.out or args.profile
    if out:
        write_profile_json(updated, out)
    _print_json(packet)


def cmd_memory_get(args: argparse.Namespace) -> None:
    _print_json(get_user_memory(args.memory))


def cmd_memory_update(args: argparse.Namespace) -> None:
    patch = _read_json_arg(args.json, args.json_file)
    _print_json(update_user_memory(args.memory, patch))


def cmd_pack_context(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = _load_profile(args.profile)
    memory = get_user_memory(args.memory) if args.memory else None
    exercises = read_exercises_jsonl(args.exercises) if args.exercises else None
    _print_json(
        pack_teaching_context(
            graph,
            profile=profile,
            user_memory=memory,
            exercises=exercises,
            mode=args.mode,
            exercise_id=args.exercise_id,
            target_node=args.target_node,
            query=args.query,
            token_budget=args.token_budget,
        )
    )


def cmd_attempts(args: argparse.Namespace) -> None:
    _print_json({"attempts": read_attempts(args.attempts, limit=args.limit)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent I/O tools for the Pi-centered learning agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("node")
    p.add_argument("--graph", required=True)
    p.add_argument("query")
    p.add_argument("--profile")
    p.add_argument("--fields")
    p.add_argument("--include-relatives", action="store_true")
    p.add_argument("--no-sources", action="store_true")
    p.add_argument("--no-user-state", action="store_true")
    p.set_defaults(func=cmd_node)

    p = sub.add_parser("relatives")
    p.add_argument("--graph", required=True)
    p.add_argument("node")
    p.add_argument("--profile")
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--direction", choices=["parents", "children", "both"], default="both")
    p.add_argument("--relation-types")
    p.add_argument("--unpack", action="store_true")
    p.set_defaults(func=cmd_relatives)

    p = sub.add_parser("first-principles")
    p.add_argument("--graph", required=True)
    p.add_argument("node")
    p.add_argument("--profile")
    p.add_argument("--max-paths", type=int, default=3)
    p.add_argument("--no-prune", action="store_true")
    p.set_defaults(func=cmd_first_principles)

    p = sub.add_parser("retrieve")
    p.add_argument("--graph", required=True)
    p.add_argument("query")
    p.add_argument("--profile")
    p.add_argument("--intent", default="teach")
    p.add_argument("--limit", type=int, default=8)
    p.set_defaults(func=cmd_retrieve)

    p = sub.add_parser("zpd")
    p.add_argument("--graph", required=True)
    p.add_argument("--profile")
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument("--mode", default="exam_sprint")
    p.set_defaults(func=cmd_zpd)

    p = sub.add_parser("path")
    p.add_argument("--graph", required=True)
    p.add_argument("--profile")
    p.add_argument("--goal-node")
    p.add_argument("--mode", default="exam_sprint")
    p.add_argument("--max-steps", type=int, default=12)
    p.add_argument("--session-minutes", type=int, default=25)
    p.set_defaults(func=cmd_path)

    p = sub.add_parser("exercise-search")
    p.add_argument("--exercises", required=True)
    p.add_argument("--graph")
    p.add_argument("--profile")
    p.add_argument("--query")
    p.add_argument("--target-node", action="append")
    p.add_argument("--difficulty")
    p.add_argument("--max-new-concepts", type=int, default=1)
    p.add_argument("--source-priority", default="course")
    p.add_argument("--ladder-level")
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_exercise_search)

    p = sub.add_parser("exercise-get")
    p.add_argument("--exercises", required=True)
    p.add_argument("exercise_id")
    p.add_argument("--graph")
    p.add_argument("--profile")
    p.add_argument("--include-solution", action="store_true")
    p.set_defaults(func=cmd_exercise_get)

    p = sub.add_parser("record-attempt")
    p.add_argument("--attempts", required=True)
    p.add_argument("--json")
    p.add_argument("--json-file")
    p.set_defaults(func=cmd_record_attempt)

    p = sub.add_parser("attempts")
    p.add_argument("--attempts", required=True)
    p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_attempts)

    p = sub.add_parser("update-learner")
    p.add_argument("--profile")
    p.add_argument("--out")
    p.add_argument("--graph")
    p.add_argument("--mode", choices=["bkt", "linear"], default="bkt")
    p.add_argument("--json")
    p.add_argument("--json-file")
    p.set_defaults(func=cmd_update_learner)

    p = sub.add_parser("memory-get")
    p.add_argument("--memory", required=True)
    p.set_defaults(func=cmd_memory_get)

    p = sub.add_parser("memory-update")
    p.add_argument("--memory", required=True)
    p.add_argument("--json")
    p.add_argument("--json-file")
    p.set_defaults(func=cmd_memory_update)

    p = sub.add_parser("pack-context")
    p.add_argument("--graph", required=True)
    p.add_argument("--profile")
    p.add_argument("--memory")
    p.add_argument("--exercises")
    p.add_argument("--mode", default="guided_exercise")
    p.add_argument("--exercise-id")
    p.add_argument("--target-node")
    p.add_argument("--query")
    p.add_argument("--token-budget", type=int, default=3000)
    p.set_defaults(func=cmd_pack_context)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
