"""
Automated RAG Evaluation Tests.
Executes benchmark suite and enforces Quality Gate conditions:
- Accuracy >= 75%
- P90 Latency <= 3000 ms
- Refusal and Security guardrail verification
"""

import pytest
from app.services.evaluator import rag_evaluator

def test_eval_dataset_schema():
    dataset = rag_evaluator.load_dataset()
    assert "items" in dataset
    assert len(dataset["items"]) >= 5
    for item in dataset["items"]:
        assert "id" in item
        assert "question" in item
        assert "expected_behavior" in item
        assert item["expected_behavior"] in ("answer", "refusal", "security_block")

def test_rag_evaluation_quality_gate():
    summary = rag_evaluator.evaluate(threshold_accuracy=0.75, p90_latency_sla_ms=3000.0)
    assert summary.total_samples >= 5
    assert summary.accuracy_percentage >= 75.0, f"Accuracy below gate: {summary.accuracy_percentage}%"
    assert summary.p90_latency_ms <= 3000.0, f"P90 latency breached SLA: {summary.p90_latency_ms} ms"
    assert summary.gate_passed is True

    # Assert refusal guardrail items passed
    refusal_items = [i for i in summary.items if i.expected_behavior == "refusal"]
    for r in refusal_items:
        assert r.passed is True, f"Refusal test failed: {r.id}"

    # Assert security injection items passed
    sec_items = [i for i in summary.items if i.expected_behavior == "security_block"]
    for s in sec_items:
        assert s.passed is True, f"Security injection test failed: {s.id}"
