import re

from src.audit.models import (
    ExtractedDeadline,
    ExtractedWarranty,
)
from src.chunking.models import ParsedChunk
from src.db.models import SeveridadeAlerta
from src.retrieval.rrf import RankedCandidate


class RiskAlert:
    """Representação de um alerta de risco em conformidade com RN-05 e RN-07."""

    def __init__(
        self,
        tipo: str,
        descricao: str,
        item_edital: str | None,
        referencia_legal: str,
        severidade: SeveridadeAlerta = SeveridadeAlerta.MEDIA,
    ) -> None:
        self.tipo = tipo
        # RN-07: Linguagem de apoio e sugestão, nunca parecer jurídico taxativo
        prefixo = "Sugestão de Revisão Humana: "
        if not descricao.startswith(prefixo):
            self.descricao = f"{prefixo}{descricao}"
        else:
            self.descricao = descricao
        self.item_edital = item_edital
        self.referencia_legal = referencia_legal
        self.severidade = severidade


class RiskDetector:
    """Motor de detecção de possíveis incompatibilidades com a Lei nº 14.133/2021 (RF-15, RN-05, RN-07, CA-10)."""

    def analyze_risks(
        self,
        chunks: list[ParsedChunk | RankedCandidate],
        deadlines: list[ExtractedDeadline] | None = None,
        warranty: ExtractedWarranty | None = None,
    ) -> list[RiskAlert]:
        """Varre os prazos e cláusulas identificando potenciais divergências com a legislação vigente."""
        alerts: list[RiskAlert] = []

        # 1. Auditoria de Prazos Processuais (Impugnação e Propostas)
        if deadlines:
            for d in deadlines:
                tipo_lower = d.tipo.lower()

                # Análise de Prazo de Impugnação (Art. 164)
                if "impugna" in tipo_lower:
                    dias_match = re.search(r"(\d+)", d.prazo_valor)
                    dias = int(dias_match.group(1)) if dias_match else 0
                    if dias < 3 or d.dias_uteis_ou_corridos == "dias corridos":
                        alerts.append(
                            RiskAlert(
                                tipo="Prazo de Impugnação Incompatível",
                                descricao=(
                                    f"O prazo de impugnação indicado ({d.prazo_valor}) aparenta ser inferior "
                                    f"ou divergir da contagem de 3 dias úteis fixada no Art. 164 da Lei nº 14.133/2021. "
                                    f"Possível incompatibilidade que merece revisão."
                                ),
                                item_edital=self._extract_item_from_citation(d.citacao),
                                referencia_legal="Art. 164 da Lei nº 14.133/2021",
                                severidade=SeveridadeAlerta.ALTA,
                            )
                        )

                # Análise de Prazo para Apresentação de Propostas (Art. 55 / CA-10)
                if "proposta" in tipo_lower or "abertura" in tipo_lower:
                    dias_match = re.search(r"(\d+)", d.prazo_valor)
                    dias = int(dias_match.group(1)) if dias_match else 0
                    if 0 < dias < 8:
                        alerts.append(
                            RiskAlert(
                                tipo="Prazo Curto para Envio de Propostas",
                                descricao=(
                                    f"O prazo de propostas fixado em {dias} dias é inferior ao mínimo legal de "
                                    f"8 dias úteis aplicável a aquisição de bens (Art. 55, I, 'a' da Lei nº 14.133/2021). "
                                    f"Sinalização para conferência das datas do certame."
                                ),
                                item_edital=self._extract_item_from_citation(d.citacao),
                                referencia_legal="Art. 55, I, 'a' da Lei nº 14.133/2021",
                                severidade=SeveridadeAlerta.ALTA,
                            )
                        )

        # 2. Auditoria da Garantia Contratual (Art. 98)
        if warranty and warranty.exigida:
            pct_match = re.search(r"(\d+(?:[\.,]\d+)?)", warranty.percentual_ou_valor)
            if pct_match:
                pct = float(pct_match.group(1).replace(",", "."))
                if pct > 10.0:
                    alerts.append(
                        RiskAlert(
                            tipo="Garantia Contratual Excessiva",
                            descricao=(
                                f"A garantia exigida de {warranty.percentual_ou_valor} supera o teto de 10% "
                                f"previsto no Art. 98 da Lei nº 14.133/2021, que apenas admite esse patamar "
                                f"em contratações de grande vulto ou complexidade com justificativa expressa."
                            ),
                            item_edital=self._extract_item_from_citation(warranty.citacao),
                            referencia_legal="Art. 98 da Lei nº 14.133/2021",
                            severidade=SeveridadeAlerta.ALTA,
                        )
                    )

        # 3. Auditoria de Exigências de Qualificação Econômico-Financeira (Art. 67)
        for chunk in chunks:
            texto_lower = chunk.texto.lower()
            if "patrimônio líquido" in texto_lower or "patrimonio liquido" in texto_lower or "capital social" in texto_lower:
                pct_match = re.search(r"(\d+(?:[\.,]\d+)?\s*%)", texto_lower)
                if pct_match:
                    num_match = re.search(r"(\d+)", pct_match.group(1))
                    if num_match and int(num_match.group(1)) > 10:
                        alerts.append(
                            RiskAlert(
                                tipo="Exigência Desproporcional de Patrimônio/Capital",
                                descricao=(
                                    f"Exigência de patrimônio líquido ou capital social de {pct_match.group(1)} "
                                    f"supera o limite máximo de 10% estipulado pelo Art. 67, § 3º da Lei nº 14.133/2021."
                                ),
                                item_edital=chunk.item or "S/N",
                                referencia_legal="Art. 67, § 3º da Lei nº 14.133/2021",
                                severidade=SeveridadeAlerta.MEDIA,
                            )
                        )

        return alerts

    @staticmethod
    def _extract_item_from_citation(citacao: str) -> str:
        match = re.search(r"item\s+([^\]]+)", citacao)
        if match:
            return match.group(1).strip()
        return "S/N"
