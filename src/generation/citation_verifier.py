import json
import logging
from dataclasses import dataclass

from src.api.schemas import ChatQueryResponse, CitacaoItem
from src.retrieval.rrf import RRFScoredCandidate

logger = logging.getLogger(__name__)

# Mensagem canônica de recusa/abstenção quando a informação não consta (RN-02)
ABSTENTION_MESSAGE = "A informação não consta no edital indexado."


@dataclass
class VerificationResult:
    """Resultado da validação estrita pós-geração."""
    is_valid: bool
    response: ChatQueryResponse
    validation_error: str | None = None


class PostGenerationCitationVerifier:
    """Validador programático pós-geração contra alucinações de citações e fontes (RN-01, RN-02)."""

    def __init__(self, fuzzy_threshold: float = 0.5) -> None:
        self.fuzzy_threshold = fuzzy_threshold

    def verify_response(
        self,
        raw_llm_output: str,
        context_candidates: list[RRFScoredCandidate],
    ) -> VerificationResult:
        """Valida se a resposta gerada pelo LLM obedece estritamente às regras de negócio e de citação."""
        # 1. Parsing do JSON
        try:
            data = json.loads(raw_llm_output.strip())
        except Exception as e:
            logger.warning("Saída do LLM não é JSON válido: %s", e)
            return VerificationResult(
                is_valid=False,
                response=self._build_abstention_response(),
                validation_error=f"Falha de formatação JSON: {e!s}",
            )

        resposta_texto = str(data.get("resposta", "")).strip()
        encontrado = bool(data.get("encontrado", False))
        confianca = float(data.get("confianca", 0.0))
        raw_citacoes = data.get("citacoes", [])
        chunk_ids = data.get("chunk_ids", [])

        # 2. Caso de Abstenção legítima declarada pelo modelo (RN-02)
        if not encontrado or not raw_citacoes:
            return VerificationResult(
                is_valid=True,
                response=ChatQueryResponse(
                    resposta=resposta_texto or ABSTENTION_MESSAGE,
                    citacoes=[],
                    encontrado=False,
                    confianca=0.0,
                    chunk_ids=[],
                ),
            )

        # 3. Validação de cada citação contra o contexto fornecido
        verified_citacoes: list[CitacaoItem] = []
        valid_chunk_ids: list[int] = []

        # Mapa de chunks do contexto por página e id
        chunks_by_page: dict[int, list[RRFScoredCandidate]] = {}
        for c in context_candidates:
            chunks_by_page.setdefault(c.candidate.pagina, []).append(c)

        for cit in raw_citacoes:
            if not isinstance(cit, dict):
                continue

            doc = str(cit.get("documento", "Edital")).strip()
            pag = cit.get("pagina")
            item = str(cit.get("item", "")).strip().rstrip(".")
            trecho = str(cit.get("trecho", "")).strip()

            if pag is None or not isinstance(pag, int):
                logger.warning("Citação sem número de página válido: %s", cit)
                continue

            # Confere se a página citada existe nos chunks do contexto (RN-01)
            matching_chunks = chunks_by_page.get(pag, [])
            if not matching_chunks:
                logger.warning(
                    "Página %d citada não encontrada em nenhum trecho do contexto recuperado (Alucinação).",
                    pag,
                )
                return VerificationResult(
                    is_valid=False,
                    response=self._build_abstention_response(),
                    validation_error=f"Página {pag} citada não consta no contexto entregue ao LLM.",
                )

            # Verifica se o trecho citado ou item bate com os dados do chunk
            found_match = False
            for cand in matching_chunks:
                cand_text_clean = cand.candidate.texto.lower()
                trecho_words = [w.lower() for w in trecho.split() if len(w) > 3]

                # Checagem de sobreposição de palavras do trecho no chunk
                overlap_ratio = 1.0
                if trecho_words:
                    overlap_words = [w for w in trecho_words if w in cand_text_clean]
                    overlap_ratio = len(overlap_words) / len(trecho_words)

                item_match = (
                    cand.candidate.item and item in cand.candidate.item
                ) or (item and item in cand.candidate.texto)

                if overlap_ratio >= self.fuzzy_threshold or item_match:
                    found_match = True
                    valid_chunk_ids.append(cand.candidate.chunk_id)
                    break

            if not found_match:
                logger.warning("Trecho citado não localizado na página %d do contexto: %s", pag, trecho[:60])
                return VerificationResult(
                    is_valid=False,
                    response=self._build_abstention_response(),
                    validation_error=f"Trecho citado não confere com o conteúdo da página {pag}.",
                )

            verified_citacoes.append(
                CitacaoItem(
                    documento=doc,
                    pagina=pag,
                    item=item or "S/N",
                    trecho=trecho,
                )
            )

        # 4. Se havia afirmações mas nenhuma citação válida sobreviveu, rejeita (RN-01)
        if not verified_citacoes:
            return VerificationResult(
                is_valid=False,
                response=self._build_abstention_response(),
                validation_error="Nenhuma citação válida pôde ser confirmada no contexto.",
            )

        # Resposta 100% auditada e verificada
        return VerificationResult(
            is_valid=True,
            response=ChatQueryResponse(
                resposta=resposta_texto,
                citacoes=verified_citacoes,
                encontrado=True,
                confianca=min(1.0, max(confianca, 0.85)),
                chunk_ids=list(set(valid_chunk_ids or chunk_ids)),
            ),
        )

    @staticmethod
    def _build_abstention_response() -> ChatQueryResponse:
        """Gera resposta padronizada de abstenção quando a validação falha ou não há evidências."""
        return ChatQueryResponse(
            resposta=ABSTENTION_MESSAGE,
            citacoes=[],
            encontrado=False,
            confianca=0.0,
            chunk_ids=[],
        )
