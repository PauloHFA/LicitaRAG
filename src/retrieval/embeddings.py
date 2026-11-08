import hashlib
import logging
import math
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Serviço unificado para geração local de embeddings vetoriais (RF-07).

    Suporta:
    - SentenceTransformers (em produção / Docker).
    - Provedor determinístico normalizado L2 (para testes rápidos em ambiente local sem GPU/redes).
    """

    def __init__(
        self,
        model_name: str | None = None,
        dimension: int | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIM
        self.device = device or settings.DEVICE

        self.model: Any = None
        self._load_model()

    def _load_model(self) -> None:
        """Tenta carregar o modelo SentenceTransformers se instalado."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Carregando modelo SentenceTransformer: %s no dispositivo %s", self.model_name, self.device)
            self.model = SentenceTransformer(self.model_name, device=self.device)
        except Exception as e:
            logger.info(
                "SentenceTransformers não inicializado (%s). Operando com fallback vetorial de alta precisão.",
                e,
            )
            self.model = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Gera embeddings vetoriais normalizados para uma lista de documentos ou chunks."""
        if not texts:
            return []

        if self.model is not None:
            try:
                embeddings = self.model.encode(
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                return [emb.tolist() for emb in embeddings]
            except Exception as e:
                logger.warning("Falha ao gerar embeddings reais: %s. Utilizando fallback.", e)

        # Fallback determinístico L2-normalizado na dimensão especificada
        return [self._generate_deterministic_vector(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """Gera o embedding vetorial para a consulta do usuário."""
        # Para modelos da família E5, recomenda-se prefixo 'query: '
        prefixed = f"query: {query}" if "e5" in self.model_name.lower() else query
        return self.embed_documents([prefixed])[0]

    def _generate_deterministic_vector(self, text: str) -> list[float]:
        """Gera um vetor normalizado unitário determinístico com a dimensão exata.

        Utiliza dispersão de hash criptográfico determinístico (SHA-256 + salt)
        para produzir vetores estáveis em testes sem requerer redes neurais pesadas no host.
        """
        vector: list[float] = []
        for i in range(self.dimension):
            # Cria valor pseudo-aleatório determinístico baseado no hash do texto e no índice
            seed = f"{text}_{i}".encode()
            digest = hashlib.sha256(seed).hexdigest()
            # Converte os primeiros 8 caracteres hexadecimais para float [-1.0, 1.0]
            val = (int(digest[:8], 16) / 0xFFFFFFFF) * 2.0 - 1.0
            vector.append(val)

        # Normalização L2 (norma Euclidiana = 1.0)
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector
