import logging
import re
from typing import Any

from src.config import settings
from src.retrieval.rrf import RRFScoredCandidate

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Reclassifica os candidatos de busca utilizando modelos Cross-Encoder (RF-09, Lacuna A4).

    Atua sobre os top candidatos do RRF, reavaliando a interação par-a-par
    entre a consulta do usuário e o texto de cada trecho.
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name or settings.RERANKER_MODEL
        self.device = device or settings.DEVICE
        self.model: Any = None
        self._load_model()

    def _load_model(self) -> None:
        """Tenta carregar o CrossEncoder se o pacote sentence_transformers estiver presente."""
        try:
            from sentence_transformers import CrossEncoder
            logger.info("Carregando CrossEncoder: %s", self.model_name)
            self.model = CrossEncoder(self.model_name, device=self.device)
        except Exception as e:
            logger.info(
                "CrossEncoder não carregado (%s). Utilizando avaliador léxico-semântico integrado.",
                e,
            )
            self.model = None

    def rerank(
        self,
        query: str,
        candidates: list[RRFScoredCandidate],
        top_k: int = 5,
    ) -> list[RRFScoredCandidate]:
        """Reordena a lista de candidatos e devolve os top_k trechos mais relevantes."""
        if not candidates:
            return []

        # 1. Se o modelo Cross-Encoder estiver disponível, executa predição neural
        if self.model is not None:
            try:
                pairs = [[query, cand.candidate.texto] for cand in candidates]
                scores = self.model.predict(pairs)
                for cand, score in zip(candidates, scores, strict=False):
                    cand.rerank_score = float(score)

                candidates.sort(key=lambda c: c.rerank_score or -999.0, reverse=True)
                return candidates[:top_k]
            except Exception as e:
                logger.warning("Falha durante inferência neural do CrossEncoder: %s", e)

        # 2. Avaliador com bônus para termos exatos, números de cláusulas e sobreposição léxica
        for cand in candidates:
            cand.rerank_score = self._compute_heuristic_rerank_score(query, cand)

        candidates.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)
        return candidates[:top_k]

    def _compute_heuristic_rerank_score(
        self,
        query: str,
        scored_cand: RRFScoredCandidate,
    ) -> float:
        """Calcula score de relevância ponderando sobreposição léxica, siglas e números de cláusula."""
        cand = scored_cand.candidate
        text_lower = cand.texto.lower()
        query_lower = query.lower()

        # Tokenização simples
        query_words = set(re.findall(r"\w+", query_lower))
        text_words = set(re.findall(r"\w+", text_lower))

        if not query_words:
            return scored_cand.rrf_score

        # Jaccard lexical básico
        overlap = len(query_words.intersection(text_words)) / len(query_words)

        bonus = 0.0

        # Bônus para números de cláusulas ou artigos procurados (ex: "14.1", "8.4")
        clause_matches = re.findall(r"\b\d+(?:\.\d+)+\b", query)
        for clause in clause_matches:
            if cand.item and clause in cand.item:
                bonus += 0.50
            elif clause in cand.texto:
                bonus += 0.30

        # Bônus para siglas em maiúsculas (ex: "CND", "NCM", "SICAF", "FGTS")
        siglas = re.findall(r"\b[A-Z]{3,6}\b", query)
        for sigla in siglas:
            if sigla in cand.texto:
                bonus += 0.40

        # Ponderação final: score RRF normalizado + sobreposição + bônus
        return (scored_cand.rrf_score * 10.0) + overlap + bonus
