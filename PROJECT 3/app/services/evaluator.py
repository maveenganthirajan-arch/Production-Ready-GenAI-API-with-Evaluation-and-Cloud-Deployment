"""
RAG Evaluation Engine.
Performs automated multi-dimensional benchmarking:
- Answer Correctness (criteria matching & semantic alignment)
- Retrieval Quality (Context Relevance to expected evidence)
- Faithfulness / Groundedness (adherence to retrieved evidence without hallucination)
- End-to-End Latency & Percentiles (Average, P90)
- Failure Rate & Quality Gate Verification
"""

import json
import os
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import numpy as np

from app.config import settings
from app.services.rag_engine import rag_engine
from app.models.schemas import EvaluationItemResult, EvaluationSummaryResponse
from app.database import SessionLocal
from app.models.sql_models import EvaluationRunLog
from app.logging_config import logger

class RAGEvaluator:
    """Evaluates RAG pipeline performance against standardized ground truth datasets."""

    def __init__(self, default_dataset_path: str = "data/eval_dataset.json"):
        self.default_dataset_path = default_dataset_path

    def load_dataset(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Loads benchmark JSON dataset."""
        target_path = path or self.default_dataset_path
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Evaluation dataset not found at {target_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate(
        self,
        dataset_path: Optional[str] = None,
        threshold_accuracy: float = 0.75,
        p90_latency_sla_ms: float = 3000.0
    ) -> EvaluationSummaryResponse:
        """
        Executes full benchmark evaluation across dataset items.
        Returns detailed summary with item-level metrics and gate status.
        """
        run_id = f"eval-{uuid.uuid4().hex[:8]}"
        dataset = self.load_dataset(dataset_path)
        items = dataset.get("items", [])

        results: List[EvaluationItemResult] = []
        latencies: List[float] = []

        total_samples = len(items)
        passed_count = 0

        for item in items:
            q_id = item["id"]
            cat = item.get("category", "General")
            question = item["question"]
            expected_behavior = item.get("expected_behavior", "answer")
            expected_evidence = item.get("expected_evidence")
            criteria = item.get("evaluation_criteria", [])
            doc_source = item.get("doc_source")

            # Execute RAG query
            t0 = time.perf_counter()
            response = rag_engine.query(question=question, user_id=f"eval_runner_{run_id}")
            t_ms = round((time.perf_counter() - t0) * 1000, 2)
            latencies.append(t_ms)

            # 1. Determine actual behavior
            if response.is_refusal:
                if "Security violation detected" in response.answer:
                    actual_behavior = "security_block"
                else:
                    actual_behavior = "refusal"
            else:
                actual_behavior = "answer"

            # 2. Context Relevance Score
            context_relevance = self._calculate_context_relevance(
                expected_behavior=expected_behavior,
                expected_evidence=expected_evidence,
                doc_source=doc_source,
                citations=response.sources
            )

            # 3. Faithfulness / Groundedness Score
            faithfulness = self._calculate_faithfulness(
                actual_behavior=actual_behavior,
                expected_behavior=expected_behavior,
                answer=response.answer,
                citations=response.sources
            )

            # 4. Answer Correctness Score
            correctness = self._calculate_correctness(
                expected_behavior=expected_behavior,
                actual_behavior=actual_behavior,
                answer=response.answer,
                criteria=criteria
            )

            # Item passes if behavior matches and correctness >= 0.70
            item_passed = (actual_behavior == expected_behavior) and (correctness >= 0.70)
            if item_passed:
                passed_count += 1

            results.append(EvaluationItemResult(
                id=q_id,
                category=cat,
                question=question,
                expected_behavior=expected_behavior,
                actual_behavior=actual_behavior,
                actual_answer=response.answer,
                context_relevance=context_relevance,
                faithfulness=faithfulness,
                correctness_score=correctness,
                latency_ms=t_ms,
                passed=item_passed
            ))

        # Compute aggregate metrics
        failed_count = total_samples - passed_count
        accuracy = round((passed_count / max(1, total_samples)) * 100, 2)
        failure_rate = round((failed_count / max(1, total_samples)) * 100, 2)
        mean_context = round(float(np.mean([r.context_relevance for r in results])), 3) if results else 0.0
        mean_faith = round(float(np.mean([r.faithfulness for r in results])), 3) if results else 0.0
        avg_lat = round(float(np.mean(latencies)), 2) if latencies else 0.0
        p90_lat = round(float(np.percentile(latencies, 90)), 2) if latencies else 0.0

        # Quality Gate condition
        gate_passed = (accuracy >= (threshold_accuracy * 100)) and (p90_lat <= p90_latency_sla_ms)

        summary = EvaluationSummaryResponse(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_samples=total_samples,
            passed_count=passed_count,
            failed_count=failed_count,
            accuracy_percentage=accuracy,
            mean_context_relevance=mean_context,
            mean_faithfulness=mean_faith,
            avg_latency_ms=avg_lat,
            p90_latency_ms=p90_lat,
            failure_rate_percentage=failure_rate,
            gate_passed=gate_passed,
            items=results
        )

        # Persist evaluation run to database
        self._persist_evaluation_log(summary)
        logger.info(f"Evaluation Run {run_id} completed: Accuracy={accuracy}%, P90 Latency={p90_lat}ms, GatePassed={gate_passed}")

        return summary

    def _calculate_context_relevance(
        self,
        expected_behavior: str,
        expected_evidence: Optional[str],
        doc_source: Optional[str],
        citations: list
    ) -> float:
        """Computes overlap score between retrieved snippets and expected ground truth."""
        if expected_behavior in ("refusal", "security_block"):
            # For refusals, absence of irrelevant context or guardrail trigger is ideal
            return 1.0

        if not citations:
            return 0.0

        # Check source document alignment
        doc_match = any(doc_source.lower() in c.doc_name.lower() for c in citations if doc_source)
        base_score = 0.5 if doc_match else 0.2

        if expected_evidence:
            evidence_words = [w.lower() for w in expected_evidence.split() if len(w) > 3]
            combined_snippets = " ".join([c.snippet.lower() for c in citations])
            matched_words = sum(1 for w in evidence_words if w in combined_snippets)
            word_ratio = matched_words / max(1, len(evidence_words))
            return round(min(1.0, base_score + (0.5 * word_ratio)), 3)

        return base_score

    def _calculate_faithfulness(
        self,
        actual_behavior: str,
        expected_behavior: str,
        answer: str,
        citations: list
    ) -> float:
        """Evaluates whether generated answer attributes source facts without hallucination."""
        if actual_behavior in ("refusal", "security_block"):
            return 1.0 if actual_behavior == expected_behavior else 0.5

        if not citations:
            return 0.2

        # Check if response has citation tags like [Doc (Page X)]
        has_provenance = ("[" in answer and "Page" in answer)
        score = 0.8 if has_provenance else 0.5

        # Check if numbers or key terms in answer appear in retrieved chunks
        answer_tokens = [w.lower() for w in answer.split() if any(c.isdigit() for c in w)]
        combined_chunks = " ".join([c.snippet.lower() for c in citations])
        token_match = sum(1 for t in answer_tokens if t in combined_chunks)
        if answer_tokens and token_match == len(answer_tokens):
            score = 1.0

        return score

    def _calculate_correctness(
        self,
        expected_behavior: str,
        actual_behavior: str,
        answer: str,
        criteria: List[str]
    ) -> float:
        """Computes criteria satisfaction ratio against expected answer components."""
        if expected_behavior != actual_behavior:
            return 0.0

        if expected_behavior in ("refusal", "security_block"):
            return 1.0

        if not criteria:
            return 1.0

        answer_lower = answer.lower()
        matched = sum(1 for crit in criteria if crit.lower() in answer_lower)
        return round(matched / len(criteria), 3)

    def _persist_evaluation_log(self, summary: EvaluationSummaryResponse):
        """Saves evaluation run history into SQLite."""
        try:
            with SessionLocal() as db:
                log_record = EvaluationRunLog(
                    run_id=summary.run_id,
                    total_samples=summary.total_samples,
                    passed_samples=summary.passed_count,
                    accuracy_score=summary.accuracy_percentage,
                    context_relevance=summary.mean_context_relevance,
                    faithfulness=summary.mean_faithfulness,
                    avg_latency_ms=summary.avg_latency_ms,
                    p90_latency_ms=summary.p90_latency_ms,
                    failure_rate_pct=summary.failure_rate_percentage
                )
                db.add(log_record)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to persist evaluation log: {e}")


# Singleton instance
rag_evaluator = RAGEvaluator()
