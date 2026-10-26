"""
FAISS Vector Store Service.
Manages in-memory and disk-persisted vector indexes with exact Inner Product (Cosine Similarity) search.
"""

import os
import pickle
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional
import faiss
import numpy as np

from app.config import settings
from app.services.embeddings import embedding_service
from app.logging_config import logger

class FAISSVectorStore:
    """FAISS vector database wrapper with persistence and metadata tracking."""

    def __init__(self, vector_dir: Optional[str] = None):
        self.vector_dir = vector_dir or settings.VECTOR_STORE_DIR
        self.index_path = os.path.join(self.vector_dir, "index.faiss")
        self.metadata_path = os.path.join(self.vector_dir, "chunks.pkl")
        self.dimension = embedding_service.dimension

        self.index: Optional[faiss.Index] = None
        self.chunks_metadata: List[Dict[str, Any]] = []
        self.last_indexed_at: Optional[str] = None

        os.makedirs(self.vector_dir, exist_ok=True)
        self.load_or_initialize()

    def load_or_initialize(self):
        """Loads existing index from disk or creates an empty IndexFlatIP."""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, "rb") as f:
                    data = pickle.load(f)
                    self.chunks_metadata = data.get("chunks", [])
                    self.last_indexed_at = data.get("timestamp")
                logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors from {self.index_path}")
                return
            except Exception as e:
                logger.error(f"Failed to load FAISS index from disk: {e}. Reinitializing.")

        # Initialize fresh Inner Product index
        self.index = faiss.IndexFlatIP(self.dimension)
        self.chunks_metadata = []
        self.last_indexed_at = None

    def add_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Embeds chunks, adds them to the FAISS index, and persists index + metadata to disk.
        Returns the number of chunks indexed.
        """
        if not chunks:
            return 0

        # Combine existing and new chunks to maintain global semantic vocabulary
        all_chunks = self.chunks_metadata + chunks
        texts = [c["text"] for c in all_chunks]
        vectors = embedding_service.embed_documents(texts)

        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(vectors)
        self.chunks_metadata = all_chunks
        self.last_indexed_at = datetime.utcnow().isoformat() + "Z"

        self.save_to_disk()
        logger.info(f"Successfully indexed {len(chunks)} chunks into FAISS. Total index count: {self.index.ntotal}")
        return len(chunks)

    def similarity_search_with_score(
        self,
        query: str,
        top_k: int = 3
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Performs inner product (cosine similarity) search on FAISS index.
        Returns list of tuples: (chunk_metadata, cosine_similarity_score).
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vector = embedding_service.embed_query(query).reshape(1, -1)
        k = min(top_k, self.index.ntotal)

        distances, indices = self.index.search(query_vector, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx < len(self.chunks_metadata):
                score = round(float(dist), 4)
                results.append((self.chunks_metadata[idx], score))

        return results

    def save_to_disk(self):
        """Persists FAISS index binary and metadata pickle."""
        if self.index is not None:
            faiss.write_index(self.index, self.index_path)
            with open(self.metadata_path, "wb") as f:
                pickle.dump({
                    "chunks": self.chunks_metadata,
                    "timestamp": self.last_indexed_at
                }, f)

    def clear(self):
        """Clears all vectors and metadata."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.chunks_metadata = []
        self.last_indexed_at = None
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.metadata_path):
            os.remove(self.metadata_path)

    def get_status(self) -> Dict[str, Any]:
        """Returns index diagnostics."""
        unique_docs = set(c.get("doc_name") for c in self.chunks_metadata)
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "total_documents": len(unique_docs),
            "embedding_dimension": self.dimension,
            "index_path": self.index_path,
            "status": "ready" if (self.index and self.index.ntotal > 0) else "empty",
            "last_indexed_at": self.last_indexed_at
        }


# Singleton instance
vector_store = FAISSVectorStore()
