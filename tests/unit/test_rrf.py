from src.retrieval.rrf import (
    RankedCandidate,
    reciprocal_rank_fusion,
)


def test_rrf_mathematical_precision():
    """Valida a precisão matemática da fórmula RRF: 1 / (60 + rank)."""
    cand1 = RankedCandidate(chunk_id=1, texto="Texto 1", pagina=1)
    cand2 = RankedCandidate(chunk_id=2, texto="Texto 2", pagina=2)

    # Vetorial: [cand1 (rank 1), cand2 (rank 2)]
    # Lexical: [cand2 (rank 1), cand1 (rank 2)]
    vector_results = [cand1, cand2]
    lexical_results = [cand2, cand1]

    fused = reciprocal_rank_fusion(vector_results, lexical_results, k=60, top_n=5)

    assert len(fused) == 2
    # Ambos tiveram rank 1 e rank 2, então devem ter o mesmo score exato:
    # 1/(60+1) + 1/(60+2) = 1/61 + 1/62 ≈ 0.016393 + 0.016129 ≈ 0.032522
    expected_score = (1.0 / 61.0) + (1.0 / 62.0)
    assert round(fused[0].rrf_score, 6) == round(expected_score, 6)
    assert round(fused[1].rrf_score, 6) == round(expected_score, 6)


def test_rrf_promotes_overlapping_candidates():
    """Valida que candidatos presentes em ambos os rankings (vetorial e lexical) superam candidatos isolados."""
    c_both = RankedCandidate(chunk_id=10, texto="Texto Presente em Ambos", pagina=5)
    c_vec_only = RankedCandidate(chunk_id=20, texto="Apenas Vetorial", pagina=6)
    c_lex_only = RankedCandidate(chunk_id=30, texto="Apenas Lexical", pagina=7)

    # c_both está em 2º no vetorial e 2º no lexical
    # c_vec_only é 1º no vetorial mas inexiste no lexical
    vector_results = [c_vec_only, c_both]
    lexical_results = [c_lex_only, c_both]

    fused = reciprocal_rank_fusion(vector_results, lexical_results, k=60)

    # c_both deve ficar no topo devido à pontuação combinada:
    # c_both: 1/62 + 1/62 = 0.032258
    # c_vec_only: 1/61 = 0.016393
    # c_lex_only: 1/61 = 0.016393
    assert fused[0].candidate.chunk_id == 10
    assert fused[0].rrf_score > fused[1].rrf_score
    assert fused[0].rank_vetorial == 2
    assert fused[0].rank_lexical == 2


def test_rrf_empty_inputs():
    """Valida comportamento robusto com listas de entrada vazias."""
    assert reciprocal_rank_fusion([], []) == []
    cand = RankedCandidate(chunk_id=1, texto="Texto", pagina=1)
    fused_vec_only = reciprocal_rank_fusion([cand], [])
    assert len(fused_vec_only) == 1
    assert fused_vec_only[0].candidate.chunk_id == 1
