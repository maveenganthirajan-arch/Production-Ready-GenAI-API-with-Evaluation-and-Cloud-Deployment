"""
Pydantic v2 Request and Response Schemas.
Enforces strict input validation, data sanitization, and output contract definitions.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# -------------------------------------------------------------
# Common Components
# -------------------------------------------------------------

class LatencyBreakdown(BaseModel):
    retrieval_ms: float = Field(..., description="Time taken to embed and retrieve vector chunks in ms")
    generation_ms: float = Field(..., description="Time taken for LLM answer synthesis in ms")
    total_ms: float = Field(..., description="End-to-end request latency in ms")


class TokenUsage(BaseModel):
    prompt_tokens: int = Field(default=0, description="Tokens used in prompt context")
    completion_tokens: int = Field(default=0, description="Tokens generated in response")
    total_tokens: int = Field(default=0, description="Total token consumption")


class SourceCitation(BaseModel):
    doc_name: str = Field(..., description="Source document file name")
    page: Optional[int] = Field(default=1, description="Page number or section")
    chunk_id: str = Field(..., description="Unique chunk identifier")
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    snippet: str = Field(..., description="Text excerpt used as grounded evidence")


# -------------------------------------------------------------
# RAG Chat Query Schemas
# -------------------------------------------------------------

class RAGQueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description="The business or operational question to answer from company documents",
        json_schema_extra={"example": "What is the standard annual paid time off (PTO) policy for full-time employees?"}
    )
    top_k: int = Field(default=3, ge=1, le=10, description="Number of evidence chunks to retrieve")
    include_sources: bool = Field(default=True, description="Whether to include source citation snippets")
    user_id: Optional[str] = Field(default="user_default", description="Optional user identifier for auditing")

    model_config = ConfigDict(extra="ignore")


class RAGQueryResponse(BaseModel):
    request_id: str = Field(..., description="Unique request tracing ID (Correlation ID)")
    question: str = Field(..., description="User's submitted question")
    answer: str = Field(..., description="Grounded, evidence-based synthesized answer or refusal")
    confidence_score: float = Field(..., description="Retrieval similarity confidence score (0.0 to 1.0)")
    is_refusal: bool = Field(..., description="True if guardrail triggered due to insufficient evidence")
    sources: List[SourceCitation] = Field(default_factory=list, description="List of source citations")
    latency: LatencyBreakdown = Field(..., description="Granular latency breakdown in milliseconds")
    usage: TokenUsage = Field(..., description="Token usage statistics")
    timestamp: str = Field(..., description="ISO 8601 timestamp of request completion")


# -------------------------------------------------------------
# Document & Vector Index Schemas
# -------------------------------------------------------------

class DocumentUploadResponse(BaseModel):
    filename: str
    chunks_created: int
    filesize_bytes: int
    status: str
    message: str


class IndexStatusResponse(BaseModel):
    total_vectors: int
    total_documents: int
    embedding_dimension: int
    index_path: str
    status: str
    last_indexed_at: Optional[str]


# -------------------------------------------------------------
# Evaluation Schemas
# -------------------------------------------------------------

class EvaluationRequest(BaseModel):
    dataset_path: Optional[str] = Field(default=None, description="Optional custom evaluation dataset path")
    threshold_accuracy: float = Field(default=0.75, ge=0.5, le=1.0, description="Minimum acceptable accuracy gate")


class EvaluationItemResult(BaseModel):
    id: str
    category: str
    question: str
    expected_behavior: str
    actual_behavior: str
    actual_answer: str
    context_relevance: float
    faithfulness: float
    correctness_score: float
    latency_ms: float
    passed: bool


class EvaluationSummaryResponse(BaseModel):
    run_id: str
    timestamp: str
    total_samples: int
    passed_count: int
    failed_count: int
    accuracy_percentage: float
    mean_context_relevance: float
    mean_faithfulness: float
    avg_latency_ms: float
    p90_latency_ms: float
    failure_rate_percentage: float
    gate_passed: bool
    items: List[EvaluationItemResult]


# -------------------------------------------------------------
# Feedback & Telemetry Schemas
# -------------------------------------------------------------

class FeedbackRequest(BaseModel):
    request_id: str = Field(..., description="The request_id of the chat response being rated")
    rating: int = Field(..., ge=-1, le=1, description="1 for positive / thumbs-up, -1 for negative / thumbs-down")
    feedback_text: Optional[str] = Field(default=None, max_length=1000, description="Optional explanation or correction")


class FeedbackResponse(BaseModel):
    status: str
    message: str


class HealthCheckResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
    vector_store_ready: bool
    database_connected: bool
    timestamp: str


class SplunkTelemetryMetricsResponse(BaseModel):
    """Matches the Splunk Observability Cloud dashboard specification."""
    total_requests: int
    total_errors: int
    errors_per_sec: float
    p90_latency_ms: float
    p50_latency_ms: float
    p99_latency_ms: float
    total_prompt_tokens: int
    total_generation_tokens: int
    active_requests: int
    cache_utilization_pct: float
    time_series_requests: List[Dict[str, Any]]
    time_series_latency: List[Dict[str, Any]]
