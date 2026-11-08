from dataclasses import dataclass, field
from typing import Any


@dataclass
class RankedCandidate:
    """Representa um chunk candidato recuperado por uma das vias de busca."""
    chunk_id: int
    texto: str
    pagina: int
    item: str | None = None
    secao: str | None = None
    tipo: str = "texto"
    confianca: float = 1.0
    documento_id: int | None = None
    score_original: float = 0.0
    metadados: dict[str, Any] = field(default_factory=dict)


@dataclass
class RRFScoredCandidate:
    """Candidato após aplicação da fusão Reciprocal Rank Fusion."""
    candidate: RankedCandidate
    rrf_score: float
    rank_vetorial: int | None = None
    rank_lexical: int | None = None
    rerank_score: float | None = None


def reciprocal_rank_fusion(
    vector_results: list[RankedCandidate],
    lexical_results: list[RankedCandidate],
    k: int = 60,
    top_n: int = 20,
) -> list[RRFScoredCandidate]:
    """Combina os rankings vetorial e lexical utilizando Reciprocal Rank Fusion (RRF).

    Fórmula:
        RRF_score(d) = sum_{m in {vector, lexical}} 1 / (k + rank_m(d))

    Onde:
        k: constante de amortecimento (padrão 60, conforme literatura de Cormack et al.).
        rank_m(d): posição 1-indexed do documento d no ranking da fonte m.
    """
    scores: dict[int, float] = {}
    candidates_by_id: dict[int, RankedCandidate] = {}
    vector_ranks: dict[int, int] = {}
    lexical_ranks: dict[int, int] = {}

    # 1. Processa ranking vetorial
    for rank, cand in enumerate(vector_results, start=1):
        cid = cand.chunk_id
        candidates_by_id[cid] = cand
        vector_ranks[cid] = rank
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))

    # 2. Processa ranking lexical
    for rank, cand in enumerate(lexical_results, start=1):
        cid = cand.chunk_id
        if cid not in candidates_by_id:
            candidates_by_id[cid] = cand
        lexical_ranks[cid] = rank
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))

    # 3. Ordena os candidatos de forma decrescente pelo score RRF
    sorted_items = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    # 4. Constrói a lista final com metadados dos rankings originais
    fused_candidates: list[RRFScoredCandidate] = []
    for cid, rrf_score in sorted_items[:top_n]:
        fused_candidates.append(
            RRFScoredCandidate(
                candidate=candidates_by_id[cid],
                rrf_score=rrf_score,
                rank_vetorial=vector_ranks.get(cid),
                rank_lexical=lexical_ranks.get(cid),
            )
        )

    return fused_candidates
