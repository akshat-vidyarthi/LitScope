import pytest
from app.ingestion.chunker import chunk_text, chunk_paper_pages, calculate_chunk_hash


def test_chunk_text_single_short_page():
    """Short page under target size should yield exactly 1 chunk."""
    text = "This is a brief abstract for a research paper on optimization methods."
    chunks = chunk_text(text, page_number=1, target_chunk_size=600)
    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["content"] == text


def test_chunk_text_multi_sentence_with_overlap():
    """Longer text should split cleanly into overlapping chunks breaking on boundaries."""
    sentences = [
        "Sentence 1 establishes the problem domain in reinforcement learning.",
        "Sentence 2 outlines the multi-agent Markov decision process formulation.",
        "Sentence 3 presents our convergence guarantees under partial observability.",
        "Sentence 4 discusses baseline comparisons against classical Q-learning.",
        "Sentence 5 describes extensive simulation experiments on robotic control.",
    ]
    long_text = " ".join(sentences * 5)
    chunks = chunk_text(long_text, page_number=2, target_chunk_size=300, chunk_overlap=60)
    assert len(chunks) > 1
    for c in chunks:
        assert c["page_number"] == 2
        assert len(c["content"]) <= 350
        assert len(c["content"]) >= 20

    # Verify overlap exists between consecutive chunks
    c1 = chunks[0]["content"]
    c2 = chunks[1]["content"]
    # Some tail of c1 should appear in c2
    overlap_snippet = c1[-30:].strip()
    assert any(word in c2 for word in overlap_snippet.split() if len(word) > 4)


def test_chunk_paper_pages_sequential_indices():
    """Verifies sequential indices and page anchoring across multiple pages."""
    pages = [
        {"page_number": 1, "content": "Page 1: Title and Introduction to graph neural networks. " * 8},
        {"page_number": 2, "content": "Page 2: Theoretical bounds, spectral graph convolutions, and proof sketches. " * 8},
    ]
    all_chunks = chunk_paper_pages(pages, target_chunk_size=250, chunk_overlap=50)
    assert len(all_chunks) >= 4

    # Verify monotonic indices
    indices = [c["chunk_index"] for c in all_chunks]
    assert indices == list(range(len(all_chunks)))

    # Verify page assignment
    p1_chunks = [c for c in all_chunks if c["page_number"] == 1]
    p2_chunks = [c for c in all_chunks if c["page_number"] == 2]
    assert len(p1_chunks) > 0
    assert len(p2_chunks) > 0
    assert len(p1_chunks) + len(p2_chunks) == len(all_chunks)


def test_chunk_hash_deterministic():
    """Hash should be identical for same input and different for altered input."""
    h1 = calculate_chunk_hash(paper_version_id=1, page_number=1, chunk_index=0, content="Sample text")
    h2 = calculate_chunk_hash(paper_version_id=1, page_number=1, chunk_index=0, content="Sample text")
    h3 = calculate_chunk_hash(paper_version_id=1, page_number=1, chunk_index=1, content="Sample text")
    assert h1 == h2
    assert h1 != h3
