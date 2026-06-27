from ai_learning_agent.kg.builder import KnowledgeGraphBuilder
from ai_learning_agent.kg.chunking import TextChunker
from ai_learning_agent.kg.extractors import JsonArrayConceptParser
from ai_learning_agent.kg.fusion import ConceptFusion
from ai_learning_agent.kg.models import ExtractedConcept, SourceChunk, SourceDocument


def test_chunker_creates_stable_chunks():
    doc = SourceDocument(
        doc_id="mazzoldi",
        title="Mazzoldi",
        text="Paragrafo uno sulla dinamica.\n\nParagrafo due sulla seconda legge di Newton.",
    )
    chunks = TextChunker(max_chars=500, overlap_chars=0).chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].doc_id == "mazzoldi"
    assert chunks[0].chunk_id.startswith("chunk:mazzoldi")


def test_json_parser_extracts_concepts():
    raw = '[{"name":"Seconda legge di Newton","formulas":["F = ma"],"aliases":["Newton second law"]}]'
    concepts = JsonArrayConceptParser().parse(raw)
    assert concepts[0].name == "Seconda legge di Newton"
    assert concepts[0].formulas == ["F = ma"]
    assert concepts[0].aliases == ["Newton second law"]


def test_concept_fusion_merges_similar_labels():
    concepts = [
        ExtractedConcept(name="Energia cinetica", description="Energia associata al moto.", formulas=["K = 1/2 m v^2"]),
        ExtractedConcept(name="energia cinetica", description="Energia del moto di un corpo.", problem_types=["problemi di energia"]),
    ]
    result = ConceptFusion().fuse(concepts)
    assert result.report.output_count == 1
    assert result.concepts[0].formulas == ["K = 1/2 m v^2"]
    assert result.concepts[0].problem_types == ["problemi di energia"]


def test_builder_preserves_sources_and_alias_fusion():
    chunk_a = SourceChunk(
        chunk_id="c1",
        doc_id="mazzoldi",
        title="Mazzoldi dinamica",
        text="La seconda legge di Newton afferma F = ma.",
        ordinal=0,
    )
    chunk_b = SourceChunk(
        chunk_id="c2",
        doc_id="alonso",
        title="Alonso dynamics",
        text="Newton's second law relates force and acceleration.",
        ordinal=0,
    )

    builder = KnowledgeGraphBuilder()
    builder.add_chunk_extraction(
        chunk_a,
        [
            ExtractedConcept(
                name="Seconda legge di Newton",
                aliases=["Newton's second law"],
                description="Relazione tra forza risultante e accelerazione.",
                prerequisites=["Vettori"],
                formulas=["F = ma"],
                problem_types=["problemi di dinamica"],
            )
        ],
    )
    builder.add_chunk_extraction(
        chunk_b,
        [
            ExtractedConcept(
                name="Newton's second law",
                aliases=["Seconda legge di Newton"],
                description="Force equals mass times acceleration.",
                related=["Force"],
            )
        ],
    )
    graph = builder.build()

    concept_nodes = [n for n in graph.nodes.values() if n.kind == "concept"]
    newton_nodes = [n for n in concept_nodes if n.label == "Seconda legge di Newton"]
    assert len(newton_nodes) == 1
    assert "Newton's second law" in newton_nodes[0].aliases
    assert len(newton_nodes[0].sources) == 2
    assert any(e.relation_type == "HAS_FORMULA" for e in graph.edges)
    assert any(e.relation_type == "REQUIRES" for e in graph.edges)
