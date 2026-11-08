from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.rrf import RankedCandidate


def test_hybrid_retriever_in_memory_search():
    """Valida o fluxo integrado de busca híbrida (vetorial + lexical + RRF + reranking)."""
    retriever = HybridRetriever()

    candidates = [
        RankedCandidate(
            chunk_id=1,
            texto="1.1 Contratação de soluções de tecnologia em nuvem pública.",
            pagina=1,
            item="1.1",
        ),
        RankedCandidate(
            chunk_id=2,
            texto="8.4.2 Comprovação de aptidão técnica mediante atestados emitidos por pessoa jurídica.",
            pagina=14,
            item="8.4.2",
        ),
        RankedCandidate(
            chunk_id=3,
            texto="14.1 O percentual de garantia contratual será de 5% sobre o valor adjudicado.",
            pagina=28,
            item="14.1",
        ),
        RankedCandidate(
            chunk_id=4,
            texto="19.1 O prazo de vigência contratual é fixado em 12 meses prorrogáveis.",
            pagina=35,
            item="19.1",
        ),
    ]

    # Pergunta específica sobre garantia
    query = "Qual é o valor e porcentagem da garantia contratual?"
    results = retriever.search_in_memory(
        query=query,
        candidates=candidates,
        top_candidates=4,
        top_final=2,
    )

    assert len(results) == 2
    # O candidato 3 (Garantia) deve ser selecionado como o primeiro
    assert results[0].candidate.chunk_id == 3
    assert results[0].candidate.item == "14.1"
    assert results[0].rrf_score > 0
    assert results[0].rerank_score is not None
    assert results[0].candidate.pagina == 28


def test_hybrid_retriever_technical_qualification():
    """Valida busca híbrida para perguntas sobre atestados e qualificação técnica."""
    retriever = HybridRetriever()

    candidates = [
        RankedCandidate(
            chunk_id=1,
            texto="1.1 Fornecimento de computadores portáteis tipo notebook.",
            pagina=2,
            item="1.1",
        ),
        RankedCandidate(
            chunk_id=2,
            texto="8.4 Qualificação Técnica: apresentar certidão de registro no CREA e atestado.",
            pagina=11,
            item="8.4",
        ),
    ]

    query = "Quais documentos de qualificação técnica e atestado CREA são exigidos?"
    results = retriever.search_in_memory(
        query=query,
        candidates=candidates,
        top_candidates=2,
        top_final=1,
    )

    assert len(results) == 1
    assert results[0].candidate.chunk_id == 2
    assert results[0].candidate.item == "8.4"
