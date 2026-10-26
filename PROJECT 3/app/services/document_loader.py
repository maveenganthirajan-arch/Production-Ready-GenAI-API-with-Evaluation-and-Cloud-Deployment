"""
Document Loader Service.
Parses PDF and TXT enterprise documents, extracting text with page-level provenance.
"""

import os
from typing import List, Dict, Any
from pypdf import PdfReader
from app.logging_config import logger

class DocumentLoader:
    """Loads and extracts text from PDF and TXT files."""

    @staticmethod
    def load_file(file_path: str) -> List[Dict[str, Any]]:
        """
        Extracts content from a file.
        Returns a list of page/section dictionaries:
        [{"text": str, "doc_name": str, "page": int}]
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        pages_content = []

        try:
            if ext == ".pdf":
                reader = PdfReader(file_path)
                for page_idx, page in enumerate(reader.pages):
                    raw_text = page.extract_text() or ""
                    cleaned = " ".join(raw_text.split())
                    if cleaned:
                        pages_content.append({
                            "text": cleaned,
                            "doc_name": filename,
                            "page": page_idx + 1
                        })

            elif ext in (".txt", ".md", ".json"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                cleaned = " ".join(content.split())
                if cleaned:
                    pages_content.append({
                        "text": cleaned,
                        "doc_name": filename,
                        "page": 1
                    })

            else:
                logger.warning(f"Unsupported file format: {ext} for {filename}")

        except Exception as e:
            logger.error(f"Error reading document {file_path}: {str(e)}")
            raise e

        return pages_content

    @classmethod
    def load_directory(cls, dir_path: str) -> List[Dict[str, Any]]:
        """Loads all supported documents in a directory."""
        all_pages = []
        if not os.path.exists(dir_path):
            return all_pages

        for fname in os.listdir(dir_path):
            if fname.lower().endswith((".pdf", ".txt", ".md")):
                full_path = os.path.join(dir_path, fname)
                pages = cls.load_file(full_path)
                all_pages.extend(pages)

        return all_pages
