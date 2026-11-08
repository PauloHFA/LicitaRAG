"""Módulo gerador de Dossiê Executivo de Auditoria Preventiva de Editais.

Consolida em um documento único todos os achados do Licita-RAG:
- Cronograma e Prazos críticos (dias úteis vs. dias corridos)
- Checklist de Habilitação nos 4 eixos legais
- Matriz de Riscos e Inconsistências frente à Lei nº 14.133/2021
- Histórico de Erratas e Cláusulas Retificadas
- Recomendações Táticas para a Sessão Pública
"""

from datetime import datetime

from src.audit.models import (
    ExtractedChecklistItem,
    ExtractedDeadline,
    ExtractedPenalty,
    ExtractedWarranty,
)
from src.audit.risk_detector import RiskAlert
from src.audit.version_diff import ClauseDiff


class AuditReportGenerator:
    """Gerador do Dossiê Executivo Consolidado de Auditoria."""

    @staticmethod
    def generate_dossier(
        edital_numero: str,
        orgao: str,
        objeto: str,
        deadlines: list[ExtractedDeadline],
        penalties: list[ExtractedPenalty],
        warranty: ExtractedWarranty | None,
        checklist: list[ExtractedChecklistItem],
        alerts: list[RiskAlert],
        diffs: list[ClauseDiff] | None = None,
    ) -> str:
        """Gera o relatório executivo completo em formato Markdown estruturado."""
        data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")

        # 1. Tabela de Prazos
        prazos_md = []
        if deadlines:
            prazos_md.append("| Evento / Prazo | Tipo | Duração | Citação |")
            prazos_md.append("|---|---|---|---|")
            for d in deadlines:
                prazos_md.append(f"| {d.tipo} | {d.dias_uteis_ou_corridos} | {d.prazo_valor} | `{d.citacao}` |")
        else:
            prazos_md.append("*Nenhum prazo explícito extraído do documento.*")

        # 2. Tabela de Garantia e Sanções
        garantia_str = (
            f"**Exigida:** Sim ({warranty.percentual_ou_valor}) - `{warranty.citacao}`"
            if warranty and warranty.exigida
            else "**Garantia:** Não exigida expressamente ou percentual padrão."
        )

        sancoes_md = []
        if penalties:
            sancoes_md.append("| Sanção Administrativa | Detalhes | Citação |")
            sancoes_md.append("|---|---|---|")
            for p in penalties:
                sancoes_md.append(f"| {p.tipo} | {p.descricao[:80]}... | `{p.citacao}` |")
        else:
            sancoes_md.append("*Nenhuma sanção atípica mapeada.*")

        # 3. Checklist de Habilitação (4 eixos)
        checklist_md = []
        if checklist:
            checklist_md.append("| Eixo Legal | Requisito Exigido | Obrigatório | Citação de Origem |")
            checklist_md.append("|---|---|:---:|---|")
            for item in checklist:
                obr = "Sim" if item.obrigatorio else "Não"
                checklist_md.append(f"| **{item.categoria}** | {item.descricao} | {obr} | `{item.citacao}` |")
        else:
            checklist_md.append("*Nenhum requisito de habilitação indexado.*")

        # 4. Matriz de Riscos (Lei 14.133/2021)
        riscos_md = []
        if alerts:
            riscos_md.append("| Severidade | Tipo de Risco | Dispositivo Legal | Sugestão Preventiva | Item Edital |")
            riscos_md.append("|:---:|---|---|---|:---:|")
            for a in alerts:
                sev_badge = f"🔴 {a.severidade.value}" if a.severidade.value == "alta" else f"🟡 {a.severidade.value}"
                riscos_md.append(f"| {sev_badge} | {a.tipo} | {a.referencia_legal} | {a.descricao} | {a.item_edital} |")
        else:
            riscos_md.append("✅ *Nenhuma incompatibilidade ou inconformidade crítica detectada com base na Lei nº 14.133/2021.*")

        # 5. Cláusulas Retificadas (se houver)
        erratas_md = []
        if diffs:
            erratas_md.append("| Cláusula | Documento | Impacto | Redação Original | Redação Retificada (Prevalece) |")
            erratas_md.append("|:---:|:---:|---|---|---|")
            for df in diffs:
                erratas_md.append(f"| **{df.item}** | {df.documento_retificador} | {df.tipo_impacto} | {df.redacao_original[:60]}... | {df.redacao_retificada[:60]}... |")
        else:
            erratas_md.append("*Nenhum aditivo ou errata conflitante identificado.*")

        dossier = f"""# 📑 DOSSIÊ EXECUTIVO DE AUDITORIA PREVENTIVA DE EDITAL
**Data da Auditoria:** {data_geracao}
**Sistema:** Licita-RAG (Auditoria Automatizada sob a Lei nº 14.133/2021)

---

## 1. IDENTIFICAÇÃO DO CERTAME
- **Instrumento Convocatório:** {edital_numero}
- **Órgão Licitante:** {orgao}
- **Objeto Resumido:** {objeto}

---

## 2. CRONOGRAMA CRÍTICO E PRAZOS PROCESSUAIS
> [!NOTE] A Nova Lei de Licitações (Lei nº 14.133/2021) adota regra geral de **dias úteis** para propostas e recursos, exceto disposições expressas de execução contratual.

{chr(10).join(prazos_md)}

### Garantias e Penalidades:
- {garantia_str}

{chr(10).join(sancoes_md)}

---

## 3. CHECKLIST INTEGRAL DE HABILITAÇÃO (ARTS. 62 A 70 DA LEI 14.133/2021)
{chr(10).join(checklist_md)}

---

## 4. MATRIZ DE RISCOS E ALERTAS DA LEI Nº 14.133/2021
> [!IMPORTANT] Todos os apontamentos abaixo representam **Sugestões de Revisão Humana** orientadas à mitigação de riscos e preservação da competitividade do licitante, sem emissão de juízo taxativo de ilegalidade (RN-07).

{chr(10).join(riscos_md)}

---

## 5. COMPARATIVO DE ERRATAS E CLÁUSULAS RETIFICADAS
{chr(10).join(erratas_md)}

---

## 6. RECOMENDAÇÕES TÁTICAS PARA O LICITANTE
1. **Documentação Prévia:** Assegurar a validade tempestiva de todas as certidões fiscais e trabalhistas listadas no checklist antes da data da abertura.
2. **Esclarecimentos e Impugnações:** Caso haja apontamentos de risco com severidade **Alta**, submeter pedido de esclarecimento ou petição de impugnação em até **3 dias úteis** antes da abertura do certame.
3. **Erratas Vigentes:** Conferir se a proposta de preços atende estritamente às redações retificadas identificadas na Seção 5.

---
*Relatório gerado automaticamente pela plataforma Licita-RAG em conformidade com as diretrizes da Lei Federal nº 14.133/2021.*
"""
        return dossier.strip()
