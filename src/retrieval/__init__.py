"""Módulo de busca híbrida (vetorial + full-text), fusão RRF e re-ranking."""
from src.retrieval.embeddings import EmbeddingService
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.rrf import (
    RankedCandidate,
    RRFScoredCandidate,
    reciprocal_rank_fusion,
)

__all__ = [
    "EmbeddingService",
    "CrossEncoderReranker",
    "HybridRetriever",
    "RankedCandidate",
    "RRFScoredCandidate",
    "reciprocal_rank_fusion",
]
