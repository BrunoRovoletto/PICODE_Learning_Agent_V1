from pathlib import Path
from tempfile import TemporaryDirectory

from ai_learning_agent.kg.models import KnowledgeEdge, KnowledgeGraph, KnowledgeNode
from ai_learning_agent.learner.graph_adapter import KnowledgeGraphLearningAdapter
from ai_learning_agent.learner.models import LearnerNodeState, LearnerProfile, PracticeObservation
from ai_learning_agent.learner.path import PathGenerator
from ai_learning_agent.learner.store import read_profile_json, write_profile_json
from ai_learning_agent.learner.tracing import MasteryTracer
from ai_learning_agent.learner.zpd import ZPDCalculator


def mini_graph() -> KnowledgeGraph:
    graph = KnowledgeGraph()
    graph.nodes = {
        "vectors": KnowledgeNode(id="vectors", label="Vettori", kind="concept", properties={"difficulty": 0.2, "mastery_threshold": 0.8}),
        "force": KnowledgeNode(id="force", label="Forza risultante", kind="concept", properties={"difficulty": 0.4, "mastery_threshold": 0.8}),
        "newton2": KnowledgeNode(id="newton2", label="Seconda legge di Newton", kind="concept", properties={"difficulty": 0.55, "mastery_threshold": 0.8, "exam_relevance": 0.9}),
        "inclined": KnowledgeNode(id="inclined", label="Piano inclinato", kind="problem_type", properties={"difficulty": 0.7, "mastery_threshold": 0.8, "estimated_minutes": 20}),
    }
    graph.edges = [
        KnowledgeEdge(source_id="force", target_id="vectors", relation_type="REQUIRES"),
        KnowledgeEdge(source_id="newton2", target_id="force", relation_type="REQUIRES"),
        KnowledgeEdge(source_id="inclined", target_id="newton2", relation_type="REQUIRES"),
    ]
    return graph


def test_bkt_tracer_updates_profile_and_gap():
    profile = LearnerProfile(learner_id="bruno")
    tracer = MasteryTracer(mode="bkt")
    profile, result = tracer.update_profile(
        profile,
        PracticeObservation(node_id="force", correct=False, mistake="forgot free-body diagram", quality=1),
    )
    state = profile.get_state("force")
    assert result.node_id == "force"
    assert state.attempts == 1
    assert state.common_mistakes == ["forgot free-body diagram"]
    assert state.gap_type == "fundamental_gap"
    assert state.next_review_at is not None


def test_zpd_blocks_nodes_until_prerequisites_mastered():
    adapter = KnowledgeGraphLearningAdapter(mini_graph())
    profile = LearnerProfile()
    zpd = ZPDCalculator(adapter).calculate(profile)
    assert any(c.node_id == "vectors" for c in zpd.ready)
    assert any(c.node_id == "force" and c.unmet_prerequisites == ["Vettori"] for c in zpd.blocked)

    profile = profile.with_state(LearnerNodeState(node_id="vectors", mastery=0.85))
    zpd = ZPDCalculator(adapter).calculate(profile)
    assert any(c.node_id == "force" for c in zpd.ready)
    assert any(c.node_id == "newton2" for c in zpd.blocked)


def test_path_generator_skips_mastered_prerequisites():
    adapter = KnowledgeGraphLearningAdapter(mini_graph())
    profile = LearnerProfile().with_state(LearnerNodeState(node_id="vectors", mastery=0.9))
    path = PathGenerator(adapter).generate_path("inclined", profile, session_minutes=30)
    assert path is not None
    assert [step.node_id for step in path.steps] == ["force", "newton2", "inclined"]
    assert path.total_minutes >= 3
    assert path.sessions


def test_mirror_view_is_overlay_not_duplicate_graph():
    adapter = KnowledgeGraphLearningAdapter(mini_graph())
    profile = LearnerProfile().with_state(LearnerNodeState(node_id="vectors", mastery=0.9))
    view = ZPDCalculator(adapter).mirror_view(profile)
    force = next(v for v in view if v.node_id == "force")
    vectors = next(v for v in view if v.node_id == "vectors")
    assert vectors.status == "mastered"
    assert force.status == "unknown"
    assert force.blocked_by == []


def test_profile_json_roundtrip():
    profile = LearnerProfile(learner_id="bruno").with_state(LearnerNodeState(node_id="vectors", mastery=0.9))
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "learner.json"
        write_profile_json(profile, path)
        loaded = read_profile_json(path)
    assert loaded.learner_id == "bruno"
    assert loaded.get_state("vectors").mastery == 0.9
