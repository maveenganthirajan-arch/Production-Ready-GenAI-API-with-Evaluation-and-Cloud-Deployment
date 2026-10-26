"""
Vector Embedding Service.
Produces normalized 384-dimensional dense semantic vectors compatible with FAISS IndexFlatIP.
Uses TF-IDF with English stop-word filtering and n-grams for high semantic discrimination.
"""

from typing import List, Optional
import os
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from app.config import settings
from app.logging_config import logger

class EmbeddingService:
    """Computes normalized dense vectors for chunks and queries."""

    def __init__(self, dimension: int = 384, vectorizer_path: Optional[str] = None):
        self.dimension = dimension
        self.vectorizer_path = vectorizer_path or os.path.join(settings.VECTOR_STORE_DIR, "vectorizer.pkl")
        self.vectorizer = TfidfVectorizer(
            max_features=dimension,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            norm="l2"
        )
        self.is_fitted = False
        self.load_if_exists()

    def load_if_exists(self):
        """Loads fitted vectorizer from disk if available."""
        if os.path.exists(self.vectorizer_path):
            try:
                with open(self.vectorizer_path, "rb") as f:
                    self.vectorizer = pickle.load(f)
                    self.is_fitted = True
                logger.info(f"Loaded existing TF-IDF vectorizer model from {self.vectorizer_path}")
            except Exception as e:
                logger.warning(f"Could not load vectorizer from disk: {e}")

    def save_to_disk(self):
        """Saves fitted vectorizer model to disk."""
        if self.is_fitted:
            with open(self.vectorizer_path, "wb") as f:
                pickle.dump(self.vectorizer, f)

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """
        Fits (if needed) and embeds texts into normalized float32 vectors of shape (len(texts), dimension).
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        # Fit vectorizer
        sparse_matrix = self.vectorizer.fit_transform(texts)
        self.is_fitted = True
        self.save_to_disk()

        dense = sparse_matrix.toarray().astype(np.float32)
        # Pad to dimension if vocabulary is smaller than dimension
        if dense.shape[1] < self.dimension:
            pad_width = ((0, 0), (0, self.dimension - dense.shape[1]))
            dense = np.pad(dense, pad_width, mode="constant", constant_values=0.0)

        # Ensure L2 normalized
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return (dense / norms).astype(np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """Embeds a single query string into a normalized dense vector of shape (dimension,)."""
        if not self.is_fitted:
            # Fallback if no documents have been indexed yet
            self.embed_documents([query, "sample baseline text for enterprise documents"])

        sparse = self.vectorizer.transform([query])
        dense = sparse.toarray().astype(np.float32)
        if dense.shape[1] < self.dimension:
            pad_width = ((0, 0), (0, self.dimension - dense.shape[1]))
            dense = np.pad(dense, pad_width, mode="constant", constant_values=0.0)

        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return (dense / norms)[0].astype(np.float32)


# Singleton instance
embedding_service = EmbeddingService(dimension=384)
