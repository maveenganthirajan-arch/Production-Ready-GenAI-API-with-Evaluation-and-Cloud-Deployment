"""
SQLAlchemy ORM models for query tracking, feedback, and evaluation runs.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime
from app.database import Base

class QueryAuditLog(Base):
    """Tracks every incoming RAG query, latency breakdown, tokens, and guardrail decisions."""
    __tablename__ = "query_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    client_ip = Column(String(45), nullable=True)
    user_id = Column(String(100), default="anonymous")
    
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    
    # Latency & Metrics
    retrieval_latency_ms = Column(Float, nullable=False)
    generation_latency_ms = Column(Float, nullable=False)
    total_latency_ms = Column(Float, nullable=False)
    
    # Tokens & Retrieval stats
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    top_k_chunks_retrieved = Column(Integer, default=0)
    top_similarity_score = Column(Float, default=0.0)
    
    # Guardrails
    guardrail_refusal = Column(Boolean, default=False)
    security_blocked = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)


class UserFeedbackLog(Base):
    """Captures human feedback (thumbs up/down, corrections) for continuous RAG improvement."""
    __tablename__ = "user_feedback_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    rating = Column(Integer, nullable=False)  # 1 (Positive) or -1 (Negative)
    feedback_text = Column(Text, nullable=True)
    user_id = Column(String(100), default="anonymous")


class EvaluationRunLog(Base):
    """Stores benchmark evaluation suite results."""
    __tablename__ = "evaluation_run_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    run_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_samples = Column(Integer, nullable=False)
    passed_samples = Column(Integer, nullable=False)
    accuracy_score = Column(Float, nullable=False)
    context_relevance = Column(Float, nullable=False)
    faithfulness = Column(Float, nullable=False)
    avg_latency_ms = Column(Float, nullable=False)
    p90_latency_ms = Column(Float, nullable=False)
    failure_rate_pct = Column(Float, nullable=False)
