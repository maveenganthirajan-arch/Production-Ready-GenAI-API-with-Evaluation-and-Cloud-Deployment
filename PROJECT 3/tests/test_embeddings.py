"""
Unit tests for Embedding Service.
Verifies dimension consistency, L2 normalization, and query embedding output.
"""

import os
import tempfile
import pytest
import numpy as np
from app.services.embeddings import EmbeddingService

@pytest.fixture
def test_embedding_service():
    with tempfile.TemporaryDirectory() as tmp_dir:
        vec_path = os.path.join(tmp_dir, "test_vectorizer.pkl")
        yield EmbeddingService(dimension=384, vectorizer_path=vec_path)

def test_embed_documents_shape_and_norm(test_embedding_service):
    texts = [
        "Cloud security policy mandates MFA for all production workloads.",
        "HR policy offers twenty days of annual leave and twelve weeks parental leave."
    ]
    vectors = test_embedding_service.embed_documents(texts)
    assert vectors.shape == (2, test_embedding_service.dimension)
    assert vectors.dtype == np.float32

    # Verify L2 normalization: norm of each vector must be approximately 1.0
    norms = np.linalg.norm(vectors, axis=1)
    for norm in norms:
        assert pytest.approx(norm, 0.01) == 1.0

def test_embed_query_shape(test_embedding_service):
    query = "What is the password rotation policy?"
    q_vec = test_embedding_service.embed_query(query)
    assert q_vec.shape == (test_embedding_service.dimension,)
    assert pytest.approx(np.linalg.norm(q_vec), 0.01) == 1.0

def test_embed_empty_documents(test_embedding_service):
    vectors = test_embedding_service.embed_documents([])
    assert vectors.shape == (0, test_embedding_service.dimension)
