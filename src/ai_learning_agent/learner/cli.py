"""CLI for the learner overlay brick."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from ai_learning_agent.kg.store import read_graph_json

from .graph_adapter import KnowledgeGraphLearningAdapter
from .models import PracticeObservation
from .path import PathGenerator
from .spaced_repetition import is_due, review_priority
from .store import read_profile_json, write_profile_json
from .tracing import MasteryTracer
from .zpd import ZPDCalculator


def cmd_update(args: argparse.Namespace) -> None:
    profile = read_profile_json(args.profile, learner_id=args.learner_id)
    obs = PracticeObservation(
        node_id=args.node_id,
        correct=args.correct,
        item_id=args.item_id,
        session_id=args.session_id,
        question_type=args.question_type,
        quality=args.quality,
        mistake=args.mistake,
    )
    tracer = MasteryTracer(mode=args.mode, mastery_threshold=args.mastery_threshold)
    profile, result = tracer.update_profile(profile, obs)
    write_profile_json(profile, args.out or args.profile)
    print(json.dumps(asdict(result), ensure_ascii=False))


def cmd_recommend(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = read_profile_json(args.profile, learner_id=args.learner_id)
    zpd = ZPDCalculator(KnowledgeGraphLearningAdapter(graph)).calculate(profile, max_results=args.max_results)
    print(json.dumps({"ability_level": zpd.ability_level, "ready": [asdict(c) for c in zpd.ready], "blocked": [asdict(c) for c in zpd.blocked]}, indent=2, ensure_ascii=False))


def cmd_path(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = read_profile_json(args.profile, learner_id=args.learner_id)
    path = PathGenerator(KnowledgeGraphLearningAdapter(graph)).generate_path(
        args.target_node_id,
        profile,
        session_minutes=args.session_minutes,
        include_review=args.include_review,
        max_steps=args.max_steps,
    )
    print(json.dumps(asdict(path) if path else None, indent=2, ensure_ascii=False))


def cmd_due(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = read_profile_json(args.profile, learner_id=args.learner_id)
    adapter = KnowledgeGraphLearningAdapter(graph)
    items = []
    for node in adapter.trackable_nodes():
        state = profile.get_state(node.id)
        if is_due(state):
            items.append({"node_id": node.id, "label": node.label, "mastery": state.mastery, "priority": review_priority(state)})
    items.sort(key=lambda x: x["priority"], reverse=True)
    print(json.dumps(items[: args.max_results], indent=2, ensure_ascii=False))


def cmd_mirror(args: argparse.Namespace) -> None:
    graph = read_graph_json(args.graph)
    profile = read_profile_json(args.profile, learner_id=args.learner_id)
    view = ZPDCalculator(KnowledgeGraphLearningAdapter(graph)).mirror_view(profile)
    print(json.dumps([asdict(v) for v in view], indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Learning Agent learner overlay brick")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("update", help="update learner mastery after one observation")
    p.add_argument("--profile", required=True)
    p.add_argument("--out")
    p.add_argument("--learner-id", default="default")
    p.add_argument("--node-id", required=True)
    p.add_argument("--correct", action="store_true")
    p.add_argument("--mode", choices=["bkt", "linear"], default="bkt")
    p.add_argument("--mastery-threshold", type=float, default=0.8)
    p.add_argument("--quality", type=int)
    p.add_argument("--mistake")
    p.add_argument("--item-id")
    p.add_argument("--session-id")
    p.add_argument("--question-type")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("recommend", help="recommend ready/ZPD nodes")
    p.add_argument("--graph", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--learner-id", default="default")
    p.add_argument("--max-results", type=int, default=10)
    p.set_defaults(func=cmd_recommend)

    p = sub.add_parser("path", help="generate prerequisite path to target node")
    p.add_argument("--graph", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--learner-id", default="default")
    p.add_argument("--target-node-id", required=True)
    p.add_argument("--session-minutes", type=int, default=35)
    p.add_argument("--include-review", action="store_true")
    p.add_argument("--max-steps", type=int)
    p.set_defaults(func=cmd_path)

    p = sub.add_parser("due", help="show due review nodes")
    p.add_argument("--graph", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--learner-id", default="default")
    p.add_argument("--max-results", type=int, default=10)
    p.set_defaults(func=cmd_due)

    p = sub.add_parser("mirror", help="render dynamic learner KG view")
    p.add_argument("--graph", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--learner-id", default="default")
    p.set_defaults(func=cmd_mirror)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
