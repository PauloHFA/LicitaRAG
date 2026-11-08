from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.rrf import RankedCandidate, RRFScoredCandidate


def test_reranker_exact_terms_and_acronyms_ca06():
    """Critério CA-06: Siglas (CND, SICAF) e números de cláusulas (14.1) devem ser priorizados."""
    reranker = CrossEncoderReranker()

    cand_generic = RankedCandidate(
        chunk_id=1,
        texto="Requisitos gerais de habilitação e regularidade das empresas participantes.",
        pagina=10,
        item="8.1",
    )
    cand_cnd = RankedCandidate(
        chunk_id=2,
        texto="Apresentação obrigatória da CND (Certidão Negativa de Débitos) da Receita Federal.",
        pagina=12,
        item="8.4.1",
    )
    cand_garantia = RankedCandidate(
        chunk_id=3,
        texto="14.1 A garantia da contratação é de 5% do valor total.",
        pagina=25,
        item="14.1",
    )

    scored_candidates = [
        RRFScoredCandidate(candidate=cand_generic, rrf_score=0.030),
        RRFScoredCandidate(candidate=cand_cnd, rrf_score=0.020),
        RRFScoredCandidate(candidate=cand_garantia, rrf_score=0.015),
    ]

    # Consulta por sigla específica CND
    query_sigla = "Quais são as exigências quanto à CND municipal e federal?"
    reranked = reranker.rerank(query=query_sigla, candidates=scored_candidates, top_k=2)

    # O candidato com a sigla CND deve ser impulsionado para a 1ª posição
    assert reranked[0].candidate.chunk_id == 2
    assert "CND" in reranked[0].candidate.texto

    # Consulta pelo item exato 14.1
    query_item = "O que estabelece a cláusula 14.1 sobre garantias?"
    reranked_item = reranker.rerank(query=query_item, candidates=scored_candidates, top_k=2)
    assert reranked_item[0].candidate.chunk_id == 3
    assert reranked_item[0].candidate.item == "14.1"


def test_reranker_empty_list():
    """Valida tolerância a lista vazia."""
    reranker = CrossEncoderReranker()
    assert reranker.rerank("qualquer consulta", []) == []
