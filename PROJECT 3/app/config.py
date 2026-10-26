"""
Application Configuration using Pydantic Settings.
Loads and validates environment variables, secrets, and system paths.
"""

import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Application Info
    APP_NAME: str = "Production-Ready GenAI RAG API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(default="production", description="Environment: development, staging, production")
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Security & Access Control
    API_KEY: str = Field(default="sk-enterprise-rag-prod-secret-key-2026", description="API Key for X-API-Key auth")
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8501"
    ]
    RATE_LIMIT_PER_MINUTE: int = 60
    ENABLE_PROMPT_INJECTION_DEFENSE: bool = True
    MASK_PII_DATA: bool = True

    # RAG & FAISS Vector Search
    VECTOR_STORE_DIR: str = "data/vector_store"
    DOCUMENTS_DIR: str = "data/sample_docs"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 3
    SIMILARITY_THRESHOLD: float = 0.15  # Below this cosine similarity, triggers refusal guardrail

    # LLM Configurations
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    MODEL_NAME: str = "gemini-1.5-flash"
    TEMPERATURE: float = 0.0

    # Persistence & Telemetry
    DATABASE_URL: str = "sqlite:///data/production_rag.db"
    ENABLE_TELEMETRY: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure critical data directories exist
os.makedirs(settings.VECTOR_STORE_DIR, exist_ok=True)
os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)
