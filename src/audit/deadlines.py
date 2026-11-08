import re

from src.audit.models import (
    ExtractedDeadline,
    ExtractedPenalty,
    ExtractedWarranty,
)
from src.chunking.models import ParsedChunk
from src.retrieval.rrf import RankedCandidate


class DeadlinesAndSanctionsExtractor:
    """Extrai e normaliza prazos, garantias e sanções administrativas do edital (RF-14, RN-06)."""

    def extract_deadlines(
        self,
        chunks: list[ParsedChunk | RankedCandidate],
        document_name: str = "Edital",
    ) -> list[ExtractedDeadline]:
        """Identifica e normaliza prazos processuais (impugnação, esclarecimentos, propostas, entrega)."""
        deadlines: list[ExtractedDeadline] = []

        patterns = [
            ("Impugnação", r"impugn.*?(?:at[ée]\s+(\d+)|(\d+)\s*(?:dias)?|(\d+)\s*\([^\)]+\))"),
            ("Esclarecimentos", r"esclarecimento.*?(?:at[ée]\s+(\d+)|(\d+)\s*(?:dias)?|(\d+)\s*\([^\)]+\))"),
            ("Validade da Proposta", r"validade\s+da(s)?\s+proposta.*?(?:(\d+)\s*(?:dias)?|(\d+)\s*\([^\)]+\))"),
            ("Prazo de Entrega", r"(?:prazo\s+de\s+)?entrega.*?(?:(\d+)\s*(?:dias)?|(\d+)\s*\([^\)]+\))"),
            ("Garantia Contratual", r"garantia.*?(?:at[ée]\s+(\d+)|(\d+)\s*(?:dias)?|(\d+)\s*\([^\)]+\))"),
        ]

        for chunk in chunks:
            texto = chunk.texto
            texto_lower = texto.lower()

            for tipo, rgx in patterns:
                if re.search(rgx, texto_lower):
                    # Normalização de dias úteis vs corridos conforme RN-06
                    modo_contagem = self._detect_day_type(texto_lower)
                    prazo_val = self._extract_deadline_value(texto_lower, tipo)

                    item_str = chunk.item or "S/N"
                    citacao = f"[{document_name}, p. {chunk.pagina}, item {item_str}]"

                    # Resumo objetivo da sentença do prazo
                    resumo = self._extract_relevant_sentence(texto, tipo)

                    deadlines.append(
                        ExtractedDeadline(
                            tipo=tipo,
                            descricao=resumo,
                            prazo_valor=prazo_val,
                            dias_uteis_ou_corridos=modo_contagem,
                            citacao=citacao,
                        )
                    )
                    break

        return deadlines

    def extract_warranty(
        self,
        chunks: list[ParsedChunk | RankedCandidate],
        document_name: str = "Edital",
    ) -> ExtractedWarranty | None:
        """Localiza e extrai as condições da garantia contratual da licitação."""
        for chunk in chunks:
            texto = chunk.texto
            texto_lower = texto.lower()

            if "garantia contratual" in texto_lower or "garantia de execução" in texto_lower:
                # Procura percentual (ex: 5%)
                pct_match = re.search(r"(\d+(?:[\.,]\d+)?\s*%)", texto)
                pct = pct_match.group(1) if pct_match else "Conforme cláusula"

                # Procura prazo de prestação
                prazo_match = re.search(r"(\d+\s*(?:\([^\)]+\)\s*)?dias\s*(?:[úu]teis|corridos)?)", texto_lower)
                prazo_txt = prazo_match.group(1) if prazo_match else "No ato da assinatura"

                item_str = chunk.item or "S/N"
                citacao = f"[{document_name}, p. {chunk.pagina}, item {item_str}]"

                return ExtractedWarranty(
                    exigida=True,
                    percentual_ou_valor=pct,
                    prazo_prestacao=prazo_txt,
                    citacao=citacao,
                )

        return None

    def extract_penalties(
        self,
        chunks: list[ParsedChunk | RankedCandidate],
        document_name: str = "Edital",
    ) -> list[ExtractedPenalty]:
        """Extrai as sanções administrativas previstas no edital."""
        penalties: list[ExtractedPenalty] = []

        penalty_types = [
            ("Advertência", r"\badvert[êe]ncia\b"),
            ("Multa Moratória", r"multa\s+(?:morat[óo]ria|de\s+\d+%)"),
            ("Multa Compensatória", r"multa\s+compensat[óo]ria"),
            ("Impedimento de Licitar", r"impedimento\s+de\s+licitar"),
            ("Declaração de Inidoneidade", r"declara[çc][ãa]o\s+de\s+inidoneidade"),
        ]

        keywords = ["sanç", "sanc", "penalidade", "multa", "inidoneidade", "impedimento", "advertência", "advertencia"]
        for chunk in chunks:
            texto_lower = chunk.texto.lower()
            if any(k in texto_lower for k in keywords):
                for nome_sancao, pattern in penalty_types:
                    if re.search(pattern, texto_lower):
                        item_str = chunk.item or "S/N"
                        citacao = f"[{document_name}, p. {chunk.pagina}, item {item_str}]"
                        sentence = self._extract_relevant_sentence(chunk.texto, nome_sancao)

                        penalties.append(
                            ExtractedPenalty(
                                tipo=nome_sancao,
                                descricao=sentence,
                                citacao=citacao,
                            )
                        )

        return penalties

    @staticmethod
    def _detect_day_type(text_lower: str) -> str:
        """Normaliza se a contagem é em dias úteis ou dias corridos (RN-06)."""
        if "dia útil" in text_lower or "dias úteis" in text_lower or "dias uteis" in text_lower:
            return "dias úteis"
        if "dia corrido" in text_lower or "dias corridos" in text_lower:
            return "dias corridos"
        if "horas" in text_lower:
            return "horas"
        return "dias corridos"

    @staticmethod
    def _extract_deadline_value(text_lower: str, tipo: str) -> str:
        """Extrai o número de dias ou valor sintético do prazo."""
        match = re.search(r"(\d+)\s*(?:\([^\)]+\)\s*)?(?:dias\s*(?:[úu]teis|corridos)?|dias)", text_lower)
        if match:
            return match.group(0).strip()
        return "Conforme cronograma"

    @staticmethod
    def _extract_relevant_sentence(text: str, keyword: str) -> str:
        """Isola a sentença mais representativa do prazo ou sanção."""
        sentences = re.split(r"[\n\.;]", text)
        kw_clean = keyword.lower().split()[0]
        for s in sentences:
            if kw_clean in s.lower() and len(s.strip()) > 15:
                return s.strip()
        return text.splitlines()[0][:160].strip()
