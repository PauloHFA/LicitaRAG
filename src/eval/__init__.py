"""Harness de avaliação sistemática: Golden Dataset, métricas de RAG e benchmark CLI."""
from src.eval.metrics import (
    EvaluationReport,
    calculate_citation_accuracy,
    calculate_faithfulness,
    calculate_mrr,
    calculate_recall_at_k,
    evaluate_abstention,
)
from src.eval.run_benchmark import BenchmarkRunner

__all__ = [
    "EvaluationReport",
    "BenchmarkRunner",
    "calculate_recall_at_k",
    "calculate_mrr",
    "calculate_citation_accuracy",
    "calculate_faithfulness",
    "evaluate_abstention",
]
