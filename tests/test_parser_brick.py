from ai_learning_agent.parser.formulas import detect_formulas
from ai_learning_agent.parser.markdown import parse_markdown_sections
from ai_learning_agent.parser.parser import PhysicsDocumentParser


SAMPLE = """# Dinamica

La dinamica studia il moto e le sue cause. La seconda legge di Newton è centrale.

$$
F = m a
$$

Questa formula collega forza risultante e accelerazione. Negli esercizi bisogna disegnare il diagramma delle forze.

## Energia

L'energia cinetica è

$K = \\frac{1}{2} m v^2$

ed è utile nei problemi di lavoro ed energia.
"""


def test_detect_formulas_finds_display_and_inline_math():
    formulas = detect_formulas(SAMPLE, doc_id="demo")
    texts = [f.text for f in formulas]
    assert any("F = m a" in text for text in texts)
    assert any("K =" in text for text in texts)


def test_parse_markdown_sections_heading_aware():
    sections = parse_markdown_sections(SAMPLE, doc_id="demo", min_section_tokens=1)
    assert len(sections) == 2
    assert sections[0].title == "Dinamica"
    assert sections[1].title == "Energia"


def test_physics_parser_outputs_formula_centered_chunks_and_kg_shape():
    document = PhysicsDocumentParser().parse_markdown(SAMPLE, title="Demo Physics", doc_id="demo")
    assert len(document.formulas) >= 2
    assert any(chunk.kind == "formula_context" for chunk in document.chunks)
    first = document.chunks[0]
    kg_shape = first.to_kg_source_chunk_dict()
    assert kg_shape["chunk_id"] == first.chunk_id
    assert kg_shape["metadata"]["parser_kind"] == first.kind
    assert "text" in kg_shape


def test_parser_chunks_are_sequentially_linked():
    document = PhysicsDocumentParser().parse_markdown(SAMPLE, title="Demo Physics", doc_id="demo")
    chunks = document.chunks
    assert chunks
    if len(chunks) > 1:
        assert chunks[0].next_chunk_id == chunks[1].chunk_id
        assert chunks[1].previous_chunk_id == chunks[0].chunk_id
