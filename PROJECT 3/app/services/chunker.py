"""
Text Chunker Service.
Splits document pages into semantic chunks with configurable size and sliding overlap.
Preserves page-level provenance metadata for precise citation attribution.
"""

from typing import List, Dict, Any
import hashlib

class TextChunker:
    """Recursively splits text into overlapping chunks while preserving provenance."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Splits a list of document pages into chunks.
        Returns:
        [
            {
                "chunk_id": str,
                "text": str,
                "doc_name": str,
                "page": int,
                "chunk_index": int,
                "char_length": int
            }
        ]
        """
        chunks = []

        for doc in documents:
            text = doc.get("text", "")
            doc_name = doc.get("doc_name", "unknown")
            page = doc.get("page", 1)

            if not text:
                continue

            # Sliding window split
            start = 0
            text_len = len(text)
            chunk_idx = 0

            while start < text_len:
                end = min(start + self.chunk_size, text_len)
                
                # Try not to cut a word in half
                if end < text_len:
                    space_pos = text.rfind(" ", start, end)
                    if space_pos != -1 and space_pos > start + (self.chunk_size * 0.7):
                        end = space_pos

                chunk_str = text[start:end].strip()

                if len(chunk_str) > 20:  # Ignore trivial snippets
                    # Generate deterministic chunk ID
                    cid_raw = f"{doc_name}:{page}:{chunk_idx}:{chunk_str[:30]}"
                    cid = hashlib.md5(cid_raw.encode("utf-8")).hexdigest()[:12]

                    chunks.append({
                        "chunk_id": f"{doc_name}_p{page}_c{chunk_idx}_{cid}",
                        "text": chunk_str,
                        "doc_name": doc_name,
                        "page": page,
                        "chunk_index": chunk_idx,
                        "char_length": len(chunk_str)
                    })
                    chunk_idx += 1

                if end >= text_len:
                    break
                start = end - self.chunk_overlap

        return chunks
