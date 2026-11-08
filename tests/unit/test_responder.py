import json

from src.generation.citation_verifier import ABSTENTION_MESSAGE
from src.generation.llm_client import MockLLMClient
from src.generation.responder import GroundedResponder
from src.retrieval.rrf import RankedCandidate, RRFScoredCandidate


def test_responder_success_with_citation_ca03():
    """Critério CA-03: Pergunta sobre garantia retorna resposta com citação verificada."""
    cand = RankedCandidate(
        chunk_id=3,
        texto="14.1 O percentual de garantia contratual será de 5% sobre o valor adjudicado.",
        pagina=28,
        item="14.1",
    )
    candidates = [RRFScoredCandidate(candidate=cand, rrf_score=0.035)]

    responder = GroundedResponder(llm_client=MockLLMClient())
    response, latencia_ms = responder.generate_response(
        query="Qual o valor da garantia contratual?",
        candidates=candidates,
    )

    assert response.encontrado is True
    assert "5%" in response.resposta
    assert len(response.citacoes) == 1
    assert response.citacoes[0].pagina == 28
    assert response.citacoes[0].item == "14.1"
    assert latencia_ms >= 0


def test_responder_abstention_ca04():
    """Critério CA-04: Pergunta sobre assunto ausente do edital aciona abstenção sem inventar dados."""
    cand = RankedCandidate(
        chunk_id=1,
        texto="1. DO OBJETO: Contratação de desenvolvimento de software.",
        pagina=1,
        item="1.1",
    )
    # Score muito baixo, simulando ausência de relevância
    candidates = [RRFScoredCandidate(candidate=cand, rrf_score=0.001)]

    responder = GroundedResponder(llm_client=MockLLMClient())
    response, _ = responder.generate_response(
        query="Existe exigência de seguro garantia para obras civis?",
        candidates=candidates,
    )

    assert response.encontrado is False
    assert response.resposta == ABSTENTION_MESSAGE
    assert response.citacoes == []


def test_responder_controlled_retry_on_failure():
    """Seção 12: Repetição controlada (1 tentativa) em caso de resposta inicial inválida."""
    cand = RankedCandidate(
        chunk_id=10,
        texto="8.4.2 Apresentar comprovação de aptidão técnica.",
        pagina=15,
        item="8.4.2",
    )
    candidates = [RRFScoredCandidate(candidate=cand, rrf_score=0.03)]

    # Mock que na primeira chamada comete alucinação de página (página 999),
    # mas que em seguida será corrigido no retry
    bad_output = json.dumps({
        "resposta": "Deve apresentar aptidão técnica.",
        "citacoes": [{"documento": "Edital", "pagina": 999, "item": "8.4.2", "trecho": "aptidão técnica"}],
        "encontrado": True,
        "confianca": 0.9,
        "chunk_ids": [10],
    })

    class RetryMockLLM(MockLLMClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
            self.calls += 1
            if self.calls == 1:
                return bad_output
            return json.dumps({
                "resposta": ABSTENTION_MESSAGE,
                "citacoes": [],
                "encontrado": False,
                "confianca": 0.0,
                "chunk_ids": [],
            })

    retry_client = RetryMockLLM()
    responder = GroundedResponder(llm_client=retry_client)

    response, _ = responder.generate_response(
        query="Quais os requisitos?",
        candidates=candidates,
    )

    # Verifica que houve 2 chamadas (tentativa inicial + 1 repetição controlada)
    assert retry_client.calls == 2
    assert response.encontrado is False
    assert response.resposta == ABSTENTION_MESSAGE
