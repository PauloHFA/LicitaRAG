import json

from src.generation.citation_verifier import ABSTENTION_MESSAGE, PostGenerationCitationVerifier
from src.retrieval.rrf import RankedCandidate, RRFScoredCandidate


def test_verifier_accepts_valid_citation():
    """Valida aceitação quando a citação e a página conferem fielmente com o contexto."""
    cand = RankedCandidate(
        chunk_id=1,
        texto="14.1 A garantia da contratação é fixada em 5% do valor total.",
        pagina=28,
        item="14.1",
    )
    context = [RRFScoredCandidate(candidate=cand, rrf_score=0.03)]

    valid_output = json.dumps({
        "resposta": "A garantia contratual exigida é de 5% do valor total.",
        "citacoes": [
            {
                "documento": "Edital",
                "pagina": 28,
                "item": "14.1",
                "trecho": "A garantia da contratação é fixada em 5% do valor total.",
            }
        ],
        "encontrado": True,
        "confianca": 0.95,
        "chunk_ids": [1],
    })

    verifier = PostGenerationCitationVerifier()
    res = verifier.verify_response(valid_output, context)

    assert res.is_valid is True
    assert res.response.encontrado is True
    assert len(res.response.citacoes) == 1
    assert res.response.citacoes[0].pagina == 28
    assert res.response.citacoes[0].item == "14.1"


def test_verifier_rejects_hallucinated_page_rn01():
    """Regra RN-01: Rejeição de resposta que alucina um número de página inexistente no contexto."""
    cand = RankedCandidate(
        chunk_id=1,
        texto="8.4 Apresentar atestado de capacidade técnica.",
        pagina=12,
        item="8.4",
    )
    context = [RRFScoredCandidate(candidate=cand, rrf_score=0.03)]

    # O LLM alucina a página 99, que não foi entregue no contexto
    hallucinated_output = json.dumps({
        "resposta": "Deve ser apresentado atestado de capacidade técnica.",
        "citacoes": [
            {
                "documento": "Edital",
                "pagina": 99,
                "item": "8.4",
                "trecho": "Apresentar atestado de capacidade técnica.",
            }
        ],
        "encontrado": True,
        "confianca": 0.90,
        "chunk_ids": [1],
    })

    verifier = PostGenerationCitationVerifier()
    res = verifier.verify_response(hallucinated_output, context)

    assert res.is_valid is False
    assert "não consta no contexto" in str(res.validation_error)
    assert res.response.resposta == ABSTENTION_MESSAGE


def test_verifier_handles_legitimate_abstention_rn02():
    """Regra RN-02: Quando o modelo responde legitimamente que a informação não consta."""
    context = [
        RRFScoredCandidate(
            candidate=RankedCandidate(chunk_id=1, texto="Objeto da licitação", pagina=1),
            rrf_score=0.01,
        )
    ]

    abstention_output = json.dumps({
        "resposta": "A informação não consta no edital indexado.",
        "citacoes": [],
        "encontrado": False,
        "confianca": 0.0,
        "chunk_ids": [],
    })

    verifier = PostGenerationCitationVerifier()
    res = verifier.verify_response(abstention_output, context)

    assert res.is_valid is True
    assert res.response.encontrado is False
    assert res.response.citacoes == []
    assert res.response.resposta == ABSTENTION_MESSAGE
