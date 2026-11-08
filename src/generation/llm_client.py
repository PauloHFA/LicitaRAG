import abc
import json
import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class LLMClient(abc.ABC):
    """Interface abstrata comum para provedores de Large Language Models (RF-10, Seção 8.3)."""

    @abc.abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        """Gera resposta em formato JSON estrito a partir dos prompts fornecidos."""
        raise NotImplementedError


class GroqClient(LLMClient):
    """Cliente para a API em nuvem da Groq (Llama 3.3 / Qwen)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "llama-3.3-70b-versatile",
    ) -> None:
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY não configurada no ambiente.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data["choices"][0]["message"]["content"])


class OllamaClient(LLMClient):
    """Cliente para o provedor local Ollama (Llama 3.1:8b ou Qwen 2.5:7b)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        url = f"{self.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data["message"]["content"])


class MockLLMClient(LLMClient):
    """Cliente simulado determinístico para testes unitários e CI sem chamadas de rede."""

    def __init__(self, predefined_response: str | dict[str, Any] | None = None) -> None:
        if isinstance(predefined_response, dict):
            self.predefined_response = json.dumps(predefined_response, ensure_ascii=False)
        else:
            self.predefined_response = predefined_response

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> str:
        if self.predefined_response is not None:
            return self.predefined_response

        # Se houver pergunta de garantia no prompt, gera resposta positiva estruturada
        if "garantia" in user_prompt.lower():
            return json.dumps({
                "resposta": "A garantia contratual exigida é de 5% do valor total adjudicado.",
                "citacoes": [
                    {
                        "documento": "Edital",
                        "pagina": 28,
                        "item": "14.1",
                        "trecho": "O percentual de garantia contratual será de 5% sobre o valor adjudicado.",
                    }
                ],
                "encontrado": True,
                "confianca": 0.95,
                "chunk_ids": [3],
            }, ensure_ascii=False)

        # Caso padrão: abstenção
        return json.dumps({
            "resposta": "A informação não consta no edital indexado.",
            "citacoes": [],
            "encontrado": False,
            "confianca": 0.0,
            "chunk_ids": [],
        }, ensure_ascii=False)


def get_llm_client(provider: str | None = None) -> LLMClient:
    """Fábrica de instâncias de clientes LLM com base na configuração do sistema."""
    chosen_provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()

    if chosen_provider == "groq" and settings.GROQ_API_KEY:
        return GroqClient()
    elif chosen_provider == "ollama":
        return OllamaClient()
    else:
        # Fallback seguro para mock caso não haja chaves ou conexão
        return MockLLMClient()
