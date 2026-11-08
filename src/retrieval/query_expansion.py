"""Módulo de Expansão Semântica de Consultas Jurídicas (Query Expansion / HyDE Lexical).

Mapeia expressões leigas ou informais dos licitantes para a terminologia técnica
e o vocabulário formal de compras públicas da Lei nº 14.133/2021.
"""

import re

LEGAL_SYNONYM_MAP: dict[str, list[str]] = {
    "dívida": ["regularidade fiscal", "certidão negativa", "cnd", "cndt", "dívida ativa", "tributária"],
    "negativado": ["regularidade fiscal", "crf", "fgts", "inadimplência", "cndt"],
    "atestado": ["qualificação técnica", "capacidade técnico-operacional", "técnico-profissional", "parcelas de maior relevância"],
    "experiência": ["atestado de capacidade técnica", "qualificação técnica", "comprovação de aptidão"],
    "garantia": ["garantia contratual", "garantia de execução", "caução", "seguro-garantia", "fiança bancária"],
    "reclamar": ["impugnação ao edital", "pedido de esclarecimento", "recurso administrativo"],
    "esclarecimento": ["pedido de esclarecimento", "impugnação", "dúvidas ao pregoeiro"],
    "dinheiro": ["qualificação econômico-financeira", "balanço patrimonial", "patrimônio líquido", "capital social"],
    "capital": ["capital social mínimo", "patrimônio líquido", "qualificação econômico-financeira"],
    "marca": ["indicação de marca", "vedação de similar", "especificação exclusiva", "equivalência"],
    "multa": ["sanções administrativas", "penalidades", "impedimento de licitar", "declaração de inidoneidade"],
    "prazo": ["dias úteis", "dias corridos", "prazo de apresentação", "impugnação", "vigência"],
}


class LegalQueryExpander:
    """Expansor léxico-semântico para maximizar o Recall@k de busca híbrida."""

    @staticmethod
    def expand_query(query: str) -> str:
        """Adiciona termos técnicos correlatos à consulta do usuário preservando a original."""
        query_clean = query.strip()
        query_lower = query_clean.lower()

        additional_terms: list[str] = []

        for key, synonyms in LEGAL_SYNONYM_MAP.items():
            if re.search(rf"\b{re.escape(key)}\b", query_lower):
                additional_terms.extend(synonyms)

        if not additional_terms:
            return query_clean

        # Remove duplicatas preservando ordem
        seen: set[str] = set(query_lower.split())
        unique_terms: list[str] = []
        for term in additional_terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique_terms.append(term)

        # Retorna a query original com termos técnicos complementares ponderados
        if unique_terms:
            return f"{query_clean} ({' '.join(unique_terms[:6])})"
        return query_clean
