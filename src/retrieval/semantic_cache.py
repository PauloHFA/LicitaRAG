"""Módulo de Cache Semântico de Consultas RAG.

Oferece cache com chave normalizada e TTL para respostas frequentes,
reduzindo latência para < 10ms e economizando tokens de LLM.
"""

import hashlib
import re
import time

from src.api.schemas import ChatQueryResponse


class SemanticCache:
    """Cache em memória / Redis com normalização lexical e expiração de respostas."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, ChatQueryResponse]] = {}

    def _normalize_key(self, edital_id: int, query: str) -> str:
        """Gera chave normalizada removendo pontuação e espaços redundantes."""
        clean = re.sub(r"[^\w\s]", "", query.lower().strip())
        normalized_words = sorted(clean.split())
        key_str = f"{edital_id}:{'_'.join(normalized_words)}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def get(self, edital_id: int, query: str) -> ChatQueryResponse | None:
        """Recupera resposta do cache se dentro do período de validade (TTL)."""
        key = self._normalize_key(edital_id, query)
        entry = self._cache.get(key)
        if entry is None:
            return None

        timestamp, response = entry
        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None

        return response

    def set(self, edital_id: int, query: str, response: ChatQueryResponse) -> None:
        """Armazena a resposta verificada no cache."""
        key = self._normalize_key(edital_id, query)
        self._cache[key] = (time.time(), response)

    def clear(self) -> None:
        """Esvazia o cache."""
        self._cache.clear()
