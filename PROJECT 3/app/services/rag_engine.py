"""
Core RAG Engine Orchestrator.
Coordinates query sanitization, vector retrieval, grounded generation,
latency instrumentation, and audit persistence.
"""

import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from app.config import settings
from app.services.vector_store import vector_store
from app.services.llm_service import llm_service, REFUSAL_MESSAGE
from app.security import detect_prompt_injection, mask_pii
from app.telemetry import telemetry
from app.database import SessionLocal
from app.models.sql_models import QueryAuditLog
from app.models.schemas import SourceCitation, LatencyBreakdown, TokenUsage, RAGQueryResponse
from app.logging_config import logger

class RAGEngine:
    """End-to-end RAG query execution pipeline with production telemetry."""

    def __init__(self):
        self.vector_store = vector_store
        self.llm_service = llm_service

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        include_sources: bool = True,
        user_id: str = "anonymous",
        request_id: Optional[str] = None
    ) -> RAGQueryResponse:
        """
        Executes complete RAG workflow:
        1. Prompt injection audit
        2. PII data masking
        3. FAISS vector retrieval & latency timing
        4. Grounded synthesis & refusal check
        5. Citation extraction
        6. Telemetry and audit logging
        """
        req_id = request_id or str(uuid.uuid4())
        k = top_k or settings.TOP_K
        t_start = time.perf_counter()

        telemetry.record_request_start()

        # Step 1: Prompt Injection Guardrail
        if detect_prompt_injection(question):
            t_end = time.perf_counter()
            total_ms = round((t_end - t_start) * 1000, 2)
            telemetry.record_request_end(total_ms, 0.0, total_ms, 10, 20, is_error=True)
            self._log_audit(req_id, user_id, question, "Security violation: Prompt injection blocked.", 0.0, total_ms, total_ms, True, False)
            
            return RAGQueryResponse(
                request_id=req_id,
                question=question,
                answer="Security violation detected: Input rejected due to prompt injection or privileged instruction override attempt.",
                confidence_score=0.0,
                is_refusal=True,
                sources=[],
                latency=LatencyBreakdown(retrieval_ms=0.0, generation_ms=total_ms, total_ms=total_ms),
                usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
                timestamp=datetime.utcnow().isoformat() + "Z"
            )

        # Step 2: PII Data Sanitization
        sanitized_question = mask_pii(question)

        # Step 3: Vector Retrieval & Timing
        t_retrieval_start = time.perf_counter()
        retrieved_items = self.vector_store.similarity_search_with_score(sanitized_question, top_k=k)
        t_retrieval_end = time.perf_counter()
        retrieval_ms = round((t_retrieval_end - t_retrieval_start) * 1000, 2)

        top_confidence = retrieved_items[0][1] if retrieved_items else 0.0

        # Step 4: Grounded Answer Synthesis & Timing
        t_gen_start = time.perf_counter()
        answer, is_refusal, prompt_tok, gen_tok = self.llm_service.generate_answer(
            question=sanitized_question,
            retrieved_chunks=retrieved_items
        )
        t_gen_end = time.perf_counter()
        generation_ms = round((t_gen_end - t_gen_start) * 1000, 2)

        total_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # Step 5: Format Source Citations
        citations = []
        if include_sources and not is_refusal:
            for chunk, score in retrieved_items:
                citations.append(SourceCitation(
                    doc_name=chunk.get("doc_name", "Unknown"),
                    page=chunk.get("page", 1),
                    chunk_id=chunk.get("chunk_id", "c0"),
                    similarity_score=score,
                    snippet=chunk.get("text", "")[:250] + "..."
                ))

        # Step 6: Record Telemetry & Audit Log
        telemetry.record_request_end(
            total_ms=total_ms,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            prompt_tokens=prompt_tok,
            generation_tokens=gen_tok,
            is_error=False
        )

        self._log_audit(
            req_id=req_id,
            user_id=user_id,
            question=question,
            answer=answer,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            total_ms=total_ms,
            security_blocked=False,
            is_refusal=is_refusal,
            prompt_tokens=prompt_tok,
            generation_tokens=gen_tok,
            top_k=len(retrieved_items),
            top_score=top_confidence
        )

        return RAGQueryResponse(
            request_id=req_id,
            question=question,
            answer=answer,
            confidence_score=top_confidence,
            is_refusal=is_refusal,
            sources=citations,
            latency=LatencyBreakdown(
                retrieval_ms=retrieval_ms,
                generation_ms=generation_ms,
                total_ms=total_ms
            ),
            usage=TokenUsage(
                prompt_tokens=prompt_tok,
                completion_tokens=gen_tok,
                total_tokens=prompt_tok + gen_tok
            ),
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    def _log_audit(
        self,
        req_id: str,
        user_id: str,
        question: str,
        answer: str,
        retrieval_ms: float,
        generation_ms: float,
        total_ms: float,
        security_blocked: bool,
        is_refusal: bool,
        prompt_tokens: int = 0,
        generation_tokens: int = 0,
        top_k: int = 0,
        top_score: float = 0.0
    ):
        """Asynchronously writes query audit record to SQLite database."""
        try:
            with SessionLocal() as db:
                log_entry = QueryAuditLog(
                    request_id=req_id,
                    user_id=user_id,
                    question=question,
                    answer=answer,
                    retrieval_latency_ms=retrieval_ms,
                    generation_latency_ms=generation_ms,
                    total_latency_ms=total_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=generation_tokens,
                    total_tokens=prompt_tokens + generation_tokens,
                    top_k_chunks_retrieved=top_k,
                    top_similarity_score=top_score,
                    guardrail_refusal=is_refusal,
                    security_blocked=security_blocked
                )
                db.add(log_entry)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")


# Singleton instance
rag_engine = RAGEngine()
