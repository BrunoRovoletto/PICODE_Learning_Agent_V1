"""Dependency-free smoke test runner for the current brick."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from test_kg_brick import (  # noqa: E402
    test_builder_preserves_sources_and_alias_fusion,
    test_chunker_creates_stable_chunks,
    test_concept_fusion_merges_similar_labels,
    test_json_parser_extracts_concepts,
)
from test_parser_brick import (  # noqa: E402
    test_detect_formulas_finds_display_and_inline_math,
    test_parse_markdown_sections_heading_aware,
    test_parser_chunks_are_sequentially_linked,
    test_physics_parser_outputs_formula_centered_chunks_and_kg_shape,
)
from test_learner_brick import (  # noqa: E402
    test_bkt_tracer_updates_profile_and_gap,
    test_mirror_view_is_overlay_not_duplicate_graph,
    test_path_generator_skips_mastered_prerequisites,
    test_profile_json_roundtrip,
    test_zpd_blocks_nodes_until_prerequisites_mastered,
)
from test_agent_io_brick import (  # noqa: E402
    test_agent_io_exercises_and_pack_context,
    test_agent_io_memory_and_attempt_log_roundtrip,
    test_agent_io_node_lookup_relatives_and_first_principles,
    test_agent_io_zpd_path_and_update_learner,
    test_context_retrieve_expands_formula_sources_and_user_state,
)

TESTS = [
    test_chunker_creates_stable_chunks,
    test_json_parser_extracts_concepts,
    test_concept_fusion_merges_similar_labels,
    test_builder_preserves_sources_and_alias_fusion,
    test_detect_formulas_finds_display_and_inline_math,
    test_parse_markdown_sections_heading_aware,
    test_physics_parser_outputs_formula_centered_chunks_and_kg_shape,
    test_parser_chunks_are_sequentially_linked,
    test_bkt_tracer_updates_profile_and_gap,
    test_zpd_blocks_nodes_until_prerequisites_mastered,
    test_path_generator_skips_mastered_prerequisites,
    test_mirror_view_is_overlay_not_duplicate_graph,
    test_profile_json_roundtrip,
    test_agent_io_node_lookup_relatives_and_first_principles,
    test_context_retrieve_expands_formula_sources_and_user_state,
    test_agent_io_zpd_path_and_update_learner,
    test_agent_io_memory_and_attempt_log_roundtrip,
    test_agent_io_exercises_and_pack_context,
]


def main() -> None:
    for test in TESTS:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(TESTS)} tests")


if __name__ == "__main__":
    main()
