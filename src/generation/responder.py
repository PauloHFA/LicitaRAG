import logging
import time

from src.api.schemas import ChatQueryResponse
from src.generation.citation_verifier import ABSTENTION_MESSAGE, PostGenerationCitationVerifier
from src.generation.llm_client import LLMClient, get_llm_client
from src.generation.prompts import (
    SYSTEM_PROMPT_BASE,
    build_user_prompt,
    format_context_for_prompt,
)
from src.retrieval.rrf import RRFScoredCandidate

logger = logging.getLogger(__name__)

# Limiar mínimo de score RRF para considerar que há evidência suficiente no edital (RN-02)
MIN_RRF_SCORE_THRESHOLD = 0.005


class GroundedResponder:
    """Orquestrador de geração fundamentada com citação estrita e validador anti-alucinação.

    Atende a RF-10, RF-11, RN-01, RN-02, RN-08 e Seção 12:
    - Isolamento de contexto como dados (<contexto>).
    - Execução do LLM com temperatura baixa (0.0).
    - Validação programática pós-geração das citações.
    - Repetição controlada (uma tentativa) em caso de falha de validação.
    - Abstenção segura quando o edital não contém a informação.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        verifier: PostGenerationCitationVerifier | None = None,
    ) -> None:
        self.llm_client = llm_client or get_llm_client()
        self.verifier = verifier or PostGenerationCitationVerifier()

    def generate_response(
        self,
        query: str,
        candidates: list[RRFScoredCandidate],
    ) -> tuple[ChatQueryResponse, int]:
        """Gera resposta auditada com citação estrita.

        Retorna (ChatQueryResponse, latencia_ms).
        """
        start_time = time.time()

        # 1. Política de Abstenção Preliminar (RN-02)
        if not candidates or max((c.rrf_score for c in candidates), default=0.0) < MIN_RRF_SCORE_THRESHOLD:
            logger.info("Nenhum candidato atingiu o limiar de relevância. Aplicando abstenção (RN-02).")
            latencia_ms = int((time.time() - start_time) * 1000)
            return (
                ChatQueryResponse(
                    resposta=ABSTENTION_MESSAGE,
                    citacoes=[],
                    encontrado=False,
                    confianca=0.0,
                    chunk_ids=[],
                ),
                latencia_ms,
            )

        # 2. Formata contexto seguro e monta o prompt
        formatted_context, context_chunk_ids = format_context_for_prompt(candidates)
        user_prompt = build_user_prompt(query, formatted_context)

        # 3. Primeira tentativa de geração
        raw_output = self.llm_client.generate(
            system_prompt=SYSTEM_PROMPT_BASE,
            user_prompt=user_prompt,
            temperature=0.0,
        )

        # 4. Validação estrita pós-geração
        verification = self.verifier.verify_response(raw_output, candidates)

        # 5. Repetição controlada (1 tentativa) se a validação falhar (Seção 12)
        if not verification.is_valid:
            logger.warning(
                "Primeira tentativa de validação falhou: %s. Acionando repetição controlada.",
                verification.validation_error,
            )

            retry_prompt = (
                f"{user_prompt}\n\n"
                f"[ATENÇÃO - CORREÇÃO OBRIGATÓRIA]: Sua resposta anterior foi REJEITADA pelo validador: "
                f"'{verification.validation_error}'. "
                f"Certifique-se de citar APENAS as páginas e itens que constam explicitamente no contexto acima. "
                f"Se a informação não estiver presente, responda com 'encontrado': false."
            )

            retry_raw_output = self.llm_client.generate(
                system_prompt=SYSTEM_PROMPT_BASE,
                user_prompt=retry_prompt,
                temperature=0.0,
            )

            verification = self.verifier.verify_response(retry_raw_output, candidates)

            # Se ainda assim falhar, aplica recusa garantida
            if not verification.is_valid:
                logger.error("Repetição controlada também falhou. Aplicando abstenção forçada.")
                verification = self.verifier.verify_response(
                    '{"resposta": "A informação não consta no edital indexado.", "citacoes": [], "encontrado": false, "confianca": 0.0, "chunk_ids": []}',
                    candidates,
                )

        latencia_ms = int((time.time() - start_time) * 1000)
        return verification.response, latencia_ms
