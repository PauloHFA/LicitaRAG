"""Módulo de geração fundamentada com citação estrita e guardrails anti-alucinação."""
from src.generation.citation_verifier import (
    ABSTENTION_MESSAGE,
    PostGenerationCitationVerifier,
    VerificationResult,
)
from src.generation.llm_client import (
    GroqClient,
    LLMClient,
    MockLLMClient,
    OllamaClient,
    get_llm_client,
)
from src.generation.prompts import (
    SYSTEM_PROMPT_BASE,
    build_user_prompt,
    format_context_for_prompt,
)
from src.generation.responder import GroundedResponder

__all__ = [
    "ABSTENTION_MESSAGE",
    "GroundedResponder",
    "PostGenerationCitationVerifier",
    "VerificationResult",
    "LLMClient",
    "GroqClient",
    "OllamaClient",
    "MockLLMClient",
    "get_llm_client",
    "SYSTEM_PROMPT_BASE",
    "format_context_for_prompt",
    "build_user_prompt",
]
