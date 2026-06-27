from pathlib import Path
from tempfile import TemporaryDirectory

from ai_learning_agent.agent_io.attempts import read_attempts, record_attempt
from ai_learning_agent.agent_io.context import pack_teaching_context
from ai_learning_agent.agent_io.exercises import Exercise, get_exercise, search_exercises, write_exercises_jsonl, read_exercises_jsonl
from ai_learning_agent.agent_io.kg_queries import get_from_first_principles, get_node, get_node_relatives
from ai_learning_agent.agent_io.learner_tools import get_learning_path, get_proximal_dev, update_learner
from ai_learning_agent.agent_io.memory import get_user_memory, update_user_memory
from ai_learning_agent.agent_io.retrieval import context_retrieve
from ai_learning_agent.kg.models import KnowledgeEdge, KnowledgeGraph, KnowledgeNode, SourceRef
from ai_learning_agent.learner.models import LearnerNodeState, LearnerProfile


def agent_io_graph() -> KnowledgeGraph:
    source = SourceRef(
        doc_id="demo_doc",
        chunk_id="chunk_1",
        title="Dinamica demo",
        source_path="demo.md",
        quote="La seconda legge di Newton afferma che la risultante delle forze è F = ma.",
    )
    graph = KnowledgeGraph()
    graph.nodes = {
        "vectors": KnowledgeNode(
            id="vectors",
            label="Vettori",
            kind="concept",
            aliases=["componenti vettoriali"],
            description="Scomposizione e somma di vettori.",
            properties={"difficulty": 0.2, "estimated_minutes": 8, "exam_relevance": 0.8},
            sources=[source],
        ),
        "force": KnowledgeNode(
            id="force",
            label="Forza risultante",
            kind="concept",
            aliases=["net force"],
            description="Somma vettoriale delle forze esterne.",
            properties={"difficulty": 0.35, "estimated_minutes": 12, "exam_relevance": 0.9},
            sources=[source],
        ),
        "newton2": KnowledgeNode(
            id="newton2",
            label="Seconda legge di Newton",
            kind="concept",
            aliases=["Newton's second law", "F = ma law"],
            description="Collega risultante delle forze e accelerazione.",
            properties={"difficulty": 0.55, "bloom_level": "apply", "extended_description": "Prima capisci la causa: forza netta cambia il moto."},
            sources=[source],
        ),
        "fma": KnowledgeNode(
            id="fma",
            label="F = ma",
            kind="formula",
            description="Formula della seconda legge.",
            properties={"difficulty": 0.4},
            sources=[source],
        ),
        "inclined": KnowledgeNode(
            id="inclined",
            label="Piano inclinato",
            kind="problem_type",
            description="Problemi con scomposizione del peso su un piano inclinato.",
            properties={"difficulty": 0.7, "estimated_minutes": 20},
            sources=[source],
        ),
    }
    graph.edges = [
        KnowledgeEdge(source_id="force", target_id="vectors", relation_type="REQUIRES", evidence="Forces require vector sums."),
        KnowledgeEdge(source_id="newton2", target_id="force", relation_type="REQUIRES", evidence="Newton II uses net force."),
        KnowledgeEdge(source_id="newton2", target_id="fma", relation_type="HAS_FORMULA", evidence="F = ma."),
        KnowledgeEdge(source_id="inclined", target_id="newton2", relation_type="REQUIRES", evidence="Inclined planes use Newton II."),
    ]
    return graph


def test_agent_io_node_lookup_relatives_and_first_principles():
    graph = agent_io_graph()
    profile = LearnerProfile().with_state(LearnerNodeState(node_id="vectors", mastery=0.9))

    node = get_node(graph, "Newton's second law", profile=profile, include_relatives=True)
    assert node["found"] is True
    assert node["node"]["id"] == "newton2"
    assert node["node"]["extended_description"].startswith("Prima capisci")
    assert "learner_state" in node["node"]

    parents = get_node_relatives(graph, "newton2", depth=1, direction="parents", unpack=False)
    assert [item["node_id"] for item in parents["relatives"] if item["via_relation"] == "REQUIRES"] == ["force"]

    both = get_node_relatives(graph, "newton2", depth=1, direction="both", unpack=True)
    assert any(item["node_id"] == "fma" and item["node"]["kind"] == "formula" for item in both["relatives"])

    first = get_from_first_principles(graph, "inclined", profile=profile)
    assert first["found"] is True
    assert first["paths"][0]["node_ids"] == ["vectors", "force", "newton2", "inclined"]


def test_context_retrieve_expands_formula_sources_and_user_state():
    graph = agent_io_graph()
    profile = LearnerProfile().with_state(LearnerNodeState(node_id="force", mastery=0.3, gap_type="fundamental_gap"))

    packet = context_retrieve(graph, "seconda legge", profile=profile, intent="teach", limit=3)
    assert any(item["node"]["id"] == "newton2" for item in packet["matched_nodes"])
    assert any(item["node_id"] == "force" for item in packet["prerequisites"])
    assert any(item["node_id"] == "fma" for item in packet["formulas"])
    assert packet["source_quotes"]


def test_agent_io_zpd_path_and_update_learner():
    graph = agent_io_graph()
    profile = LearnerProfile().with_state(LearnerNodeState(node_id="vectors", mastery=0.9))

    zpd = get_proximal_dev(graph, profile, max_results=5)
    assert any(item["node_id"] == "force" for item in zpd["ready"])
    assert any(item["node_id"] == "newton2" for item in zpd["blocked"])

    path = get_learning_path(graph, profile, goal_node="inclined", max_steps=10)
    assert path["found"] is True
    assert [step["node_id"] for step in path["path"]["steps"]] == ["force", "newton2", "inclined"]

    updated, result = update_learner(
        graph,
        profile,
        {
            "exercise_id": "ex_force_1",
            "node_evaluations": [
                {"node_id": "force", "correct": False, "quality": 1, "mistake": "forgot free-body diagram"}
            ],
        },
    )
    assert result["updates"][0]["node_id"] == "force"
    assert updated.get_state("force").attempts == 1
    assert updated.get_state("force").next_review_at is not None


def test_agent_io_memory_and_attempt_log_roundtrip():
    with TemporaryDirectory() as tmp:
        memory_path = Path(tmp) / "learner_memory.json"
        memory = get_user_memory(memory_path)
        assert memory["schema"] == "ai_learning_agent.learner_memory.v1"
        updated = update_user_memory(
            memory_path,
            {"learning_style": {"prefers": ["visual first"]}, "recurring_difficulties": ["sign conventions"]},
        )
        assert "visual first" in updated["learning_style"]["prefers"]
        assert "sign conventions" in get_user_memory(memory_path)["recurring_difficulties"]

        attempts_path = Path(tmp) / "attempts.jsonl"
        record = record_attempt(attempts_path, {"exercise_id": "ex1", "answer": "F=ma", "confidence": 0.7})
        loaded = read_attempts(attempts_path)
        assert loaded[0]["attempt_id"] == record["attempt_id"]
        assert loaded[0]["timestamp"]


def test_agent_io_exercises_and_pack_context():
    graph = agent_io_graph()
    profile = LearnerProfile().with_state(LearnerNodeState(node_id="vectors", mastery=0.9))
    exercises = [
        Exercise(
            exercise_id="ex_force_easy",
            statement="Calcola la forza risultante su un corpo con due forze orizzontali.",
            required_node_ids=["force"],
            difficulty=0.25,
            number_of_steps=1,
            exercise_ladder_level="direct_formula",
            solution_available=True,
            solution="Somma vettoriale delle forze.",
        )
    ]

    results = search_exercises(exercises, target_nodes=["force"], graph=graph, profile=profile, difficulty="easy")
    assert results[0]["exercise"]["exercise_id"] == "ex_force_easy"
    assert "solution" not in results[0]["exercise"]

    exercise_packet = get_exercise(exercises, "ex_force_easy", graph=graph, profile=profile)
    assert exercise_packet["found"] is True
    assert exercise_packet["required_nodes"][0]["id"] == "force"

    context = pack_teaching_context(
        graph,
        profile=profile,
        user_memory={"recurring_difficulties": ["free-body diagrams"]},
        exercises=exercises,
        mode="guided_exercise",
        exercise_id="ex_force_easy",
        token_budget=1200,
    )
    assert context["exercise"]["exercise"]["exercise_id"] == "ex_force_easy"
    assert context["zpd_snapshot"] is not None
    assert "free-body diagrams" in context["recent_mistakes"]

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "exercises.jsonl"
        write_exercises_jsonl(exercises, path)
        assert read_exercises_jsonl(path)[0].exercise_id == "ex_force_easy"
