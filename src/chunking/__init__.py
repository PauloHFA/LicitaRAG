"""Módulo de segmentação hierárquica por cláusula."""
from src.chunking.clause_splitter import (
    CLAUSE_REGEX,
    HierarchicalClauseSplitter,
    HierarchyTracker,
)
from src.chunking.models import ParsedChunk

__all__ = [
    "ParsedChunk",
    "HierarchicalClauseSplitter",
    "HierarchyTracker",
    "CLAUSE_REGEX",
]
