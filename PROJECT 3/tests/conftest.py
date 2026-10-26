"""
Pytest configuration and global fixtures.
Initializes database and seeds vector store with corporate sample documents before tests run.
"""

import os
import pytest
from app.database import init_db
from app.services.vector_store import vector_store
from app.services.document_loader import DocumentLoader
from app.services.chunker import TextChunker
from app.config import settings

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensures SQL schema is initialized and sample documents are indexed."""
    init_db()

    # Seed vector store if empty
    if vector_store.index is None or vector_store.index.ntotal == 0:
        docs = DocumentLoader.load_directory(settings.DOCUMENTS_DIR)
        chunker = TextChunker(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
        chunks = chunker.chunk_documents(docs)
        vector_store.add_chunks(chunks)

    yield
