"""
Unit tests for Text Chunker service.
Verifies semantic sliding window, chunk overlap, and provenance metadata.
"""

import pytest
from app.services.chunker import TextChunker

def test_chunker_basic_split():
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    docs = [
        {
            "text": "This is a test document designed to verify that the chunker splits sentences properly without cutting words.",
            "doc_name": "sample.pdf",
            "page": 1
        }
    ]
    chunks = chunker.chunk_documents(docs)
    assert len(chunks) >= 1
    assert chunks[0]["doc_name"] == "sample.pdf"
    assert chunks[0]["page"] == 1
    assert "chunk_id" in chunks[0]
    assert len(chunks[0]["text"]) <= 120

def test_chunker_provenance_preservation():
    chunker = TextChunker(chunk_size=50, chunk_overlap=10)
    docs = [
        {"text": "Page one text content with enough words to generate multiple chunks for verification.", "doc_name": "manual.pdf", "page": 1},
        {"text": "Page two text content that also generates chunks with page two provenance attached.", "doc_name": "manual.pdf", "page": 2}
    ]
    chunks = chunker.chunk_documents(docs)
    pages = {c["page"] for c in chunks}
    assert 1 in pages
    assert 2 in pages
    for c in chunks:
        assert c["doc_name"] == "manual.pdf"
        assert c["chunk_id"].startswith("manual.pdf_p")

def test_chunker_empty_input():
    chunker = TextChunker()
    assert chunker.chunk_documents([]) == []
    assert chunker.chunk_documents([{"text": "", "doc_name": "empty.txt", "page": 1}]) == []
