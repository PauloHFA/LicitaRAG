"""Módulo de comparativo semântico de versões (Edital Original vs. Erratas/Aditivos).

Identifica cláusulas alteradas, compara o texto anterior com a nova redação
e classifica o impacto prático para o licitante (financeiro, técnico, prazo ou procedimental).
"""

from dataclasses import dataclass

from src.chunking.models import ParsedChunk


@dataclass
class ClauseDiff:
    """Representa a diferença entre a redação original e a retificada de uma cláusula."""
    item: str
    pagina_original: int
    pagina_retificada: int
    redacao_original: str
    redacao_retificada: str
    documento_retificador: str
    tipo_impacto: str
    descricao_impacto: str


class VersionComparator:
    """Comparador de cláusulas retificadas entre edital base e aditivos/erratas."""

    @staticmethod
    def compare_versions(
        original_chunks: list[ParsedChunk],
        errata_chunks: list[ParsedChunk],
        document_errata_name: str = "Errata v2",
    ) -> list[ClauseDiff]:
        """Compara cláusulas coincidentes em item/seção para identificar o que foi modificado."""
        orig_map: dict[str, ParsedChunk] = {}
        for c in original_chunks:
            if c.item and c.item != "S/N":
                orig_map[c.item.strip().rstrip(".")] = c

        diffs: list[ClauseDiff] = []

        for ec in errata_chunks:
            if not ec.item or ec.item == "S/N":
                continue

            item_key = ec.item.strip().rstrip(".")
            orig = orig_map.get(item_key)

            if orig and orig.texto.strip() != ec.texto.strip():
                impacto, desc = VersionComparator._analyze_impact(orig.texto, ec.texto)
                diffs.append(
                    ClauseDiff(
                        item=item_key,
                        pagina_original=orig.pagina,
                        pagina_retificada=ec.pagina,
                        redacao_original=orig.texto.strip(),
                        redacao_retificada=ec.texto.strip(),
                        documento_retificador=document_errata_name,
                        tipo_impacto=impacto,
                        descricao_impacto=desc,
                    )
                )

        return diffs

    @staticmethod
    def _analyze_impact(old_text: str, new_text: str) -> tuple[str, str]:
        """Avalia heuristicamente o impacto da retificação (Financeiro, Prazo, Técnico ou Geral)."""
        old_l = old_text.lower()
        new_l = new_text.lower()

        # 1. Prazos
        if "prazo" in old_l or "prazo" in new_l or "dias" in old_l or "dias" in new_l:
            return "Prazo / Cronograma", "Alteração de contagem ou datas críticas do certame."

        # 2. Garantias e Valores
        if "%" in old_l or "%" in new_l or "garantia" in old_l or "garantia" in new_l:
            return "Financeiro / Garantia", "Modificação no percentual de garantia ou qualificação econômico-financeira."

        # 3. Habilitação Técnica
        if "atestado" in old_l or "técnica" in old_l or "capacidade" in old_l:
            return "Qualificação Técnica", "Alteração nas exigências de comprovação operacional ou atestados."

        return "Procedimental", "Adequação formal ou procedimental do texto da cláusula."
