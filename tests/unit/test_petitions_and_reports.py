from src.api.schemas import ChatQueryResponse, CitacaoItem
from src.audit.models import (
    ExtractedChecklistItem,
    ExtractedDeadline,
    ExtractedPenalty,
    ExtractedWarranty,
)
from src.audit.petitions import PetitionGenerator
from src.audit.report_generator import AuditReportGenerator
from src.audit.risk_detector import RiskAlert
from src.audit.version_diff import ClauseDiff, VersionComparator
from src.chunking.models import ParsedChunk
from src.db.models import SeveridadeAlerta
from src.retrieval.query_expansion import LegalQueryExpander
from src.retrieval.semantic_cache import SemanticCache


def test_petition_generator_with_alerts():
    """Valida a geração estruturada da minuta de impugnação administrativa."""
    alerts = [
        RiskAlert(
            tipo="Prazo Curto para Envio de Propostas",
            descricao="Prazo de propostas fixado em 5 dias úteis, inferior ao mínimo legal de 8 dias úteis.",
            item_edital="4.1",
            referencia_legal="Art. 55, I, 'a' da Lei nº 14.133/2021",
            severidade=SeveridadeAlerta.ALTA,
        ),
        RiskAlert(
            tipo="Garantia Contratual Excessiva",
            descricao="Garantia exigida de 15% supera o teto de 10% do Art. 98.",
            item_edital="14.1",
            referencia_legal="Art. 98 da Lei nº 14.133/2021",
            severidade=SeveridadeAlerta.ALTA,
        ),
    ]

    minuta = PetitionGenerator.generate_impugnacao(
        edital_numero="Pregão Eletrônico nº 10/2026",
        orgao="Ministério da Saúde",
        alerts=alerts,
        razao_social="Empresa Alpha Ltda.",
        cnpj="11.222.333/0001-44",
    )

    assert "ILUSTRÍSSIMO(A) SENHOR(A) AGENTE DE CONTRATAÇÃO" in minuta
    assert "Ministério da Saúde" in minuta
    assert "Pregão Eletrônico nº 10/2026" in minuta
    assert "Empresa Alpha Ltda." in minuta
    assert "Artigo 164 da Lei Federal nº 14.133/2021" in minuta
    assert "Art. 55, I, 'a'" in minuta
    assert "Art. 98" in minuta
    assert "Art. 55, § 1º" in minuta  # Pedido de reabertura de prazo


def test_petition_generator_empty_alerts():
    """Valida comportamento da minuta quando não há alertas."""
    minuta = PetitionGenerator.generate_impugnacao(
        edital_numero="PE 01/2026",
        orgao="Órgão X",
        alerts=[],
    )
    assert "Nenhum apontamento de inconformidade" in minuta


def test_audit_report_generator():
    """Valida geração do dossiê executivo consolidado com todos os módulos."""
    deadlines = [
        ExtractedDeadline(
            tipo="Abertura / Propostas",
            descricao="Recebimento em 10 dias úteis",
            prazo_valor="10 dias úteis",
            dias_uteis_ou_corridos="dias úteis",
            citacao="[Edital, p. 2, item 2.1]",
        )
    ]
    penalties = [
        ExtractedPenalty(
            tipo="Multa Moratória",
            descricao="Multa de 0,5% por dia de atraso injustificado",
            citacao="[Edital, p. 30, item 18.2]",
        )
    ]
    warranty = ExtractedWarranty(
        exigida=True,
        percentual_ou_valor="5%",
        prazo_prestacao="10 dias úteis",
        citacao="[Edital, p. 25, item 14.1]",
    )
    checklist = [
        ExtractedChecklistItem(
            categoria="Técnica",
            descricao="Atestado de capacidade técnica operacional",
            citacao="[Edital, p. 12, item 8.4]",
            obrigatorio=True,
        )
    ]
    alerts = [
        RiskAlert(
            tipo="Alerta Teste",
            descricao="Descrição teste",
            item_edital="1.1",
            referencia_legal="Art. 55",
            severidade=SeveridadeAlerta.MEDIA,
        )
    ]
    diffs = [
        ClauseDiff(
            item="14.1",
            pagina_original=25,
            pagina_retificada=2,
            redacao_original="Garantia de 10%",
            redacao_retificada="Garantia de 5%",
            documento_retificador="Errata v2",
            tipo_impacto="Financeiro / Garantia",
            descricao_impacto="Redução do percentual de garantia",
        )
    ]

    dossier = AuditReportGenerator.generate_dossier(
        edital_numero="Edital 42/2026",
        orgao="Tribunal de Justiça",
        objeto="Serviços de Nuvem e Inteligência Artificial",
        deadlines=deadlines,
        penalties=penalties,
        warranty=warranty,
        checklist=checklist,
        alerts=alerts,
        diffs=diffs,
    )

    assert "# 📑 DOSSIÊ EXECUTIVO DE AUDITORIA PREVENTIVA DE EDITAL" in dossier
    assert "Edital 42/2026" in dossier
    assert "Tribunal de Justiça" in dossier
    assert "Serviços de Nuvem" in dossier
    assert "Abertura / Propostas" in dossier
    assert "Multa Moratória" in dossier
    assert "Garantia de Execução" in dossier or "5%" in dossier
    assert "Atestado de capacidade técnica" in dossier
    assert "Errata v2" in dossier


def test_version_comparator():
    """Valida identificação de diferenças semânticas entre edital e errata."""
    orig_chunks = [
        ParsedChunk(
            texto="14.1 A garantia da contratação será de 10% do valor total.",
            pagina=20,
            item="14.1",
        ),
        ParsedChunk(
            texto="5.2 O prazo para entrega dos bens será de 15 dias corridos.",
            pagina=8,
            item="5.2",
        ),
    ]

    errata_chunks = [
        ParsedChunk(
            texto="14.1 A garantia da contratação fica retificada para 5% do valor total.",
            pagina=2,
            item="14.1",
        ),
        ParsedChunk(
            texto="5.2 O prazo para entrega dos bens será de 30 dias úteis.",
            pagina=1,
            item="5.2",
        ),
    ]

    diffs = VersionComparator.compare_versions(orig_chunks, errata_chunks, document_errata_name="Errata v2")

    assert len(diffs) == 2
    diff_map = {d.item: d for d in diffs}

    assert "14.1" in diff_map
    assert diff_map["14.1"].tipo_impacto == "Financeiro / Garantia"
    assert "10%" in diff_map["14.1"].redacao_original
    assert "5%" in diff_map["14.1"].redacao_retificada

    assert "5.2" in diff_map
    assert diff_map["5.2"].tipo_impacto == "Prazo / Cronograma"


def test_legal_query_expander():
    """Valida expansão semântica de termos leigos para terminologia da Lei 14.133."""
    expander = LegalQueryExpander()

    expanded_divida = expander.expand_query("Como participar com dívida ativa?")
    assert "regularidade fiscal" in expanded_divida
    assert "cnd" in expanded_divida

    expanded_atestado = expander.expand_query("qual o atestado necessário?")
    assert "qualificação técnica" in expanded_atestado or "capacidade técnico-operacional" in expanded_atestado

    expanded_plain = expander.expand_query("qual o objeto do contrato?")
    assert expanded_plain == "qual o objeto do contrato?"


def test_semantic_cache():
    """Valida cache de consultas frequentes com normalização e expiração."""
    cache = SemanticCache(ttl_seconds=3600)
    resp = ChatQueryResponse(
        resposta="A garantia exigida é de 5%.",
        citacoes=[CitacaoItem(documento="Edital", pagina=20, item="14.1", trecho="5%")],
        encontrado=True,
        confianca=0.95,
        chunk_ids=[1],
    )

    # Armazena
    cache.set(edital_id=1, query="Qual a garantia exigida?", response=resp)

    # Recupera com pergunta reordenada/diferente capitalização
    cached = cache.get(edital_id=1, query="Garantia qual a exigida?")
    assert cached is not None
    assert cached.resposta == "A garantia exigida é de 5%."

    # Cache miss para edital diferente ou pergunta diferente
    assert cache.get(edital_id=2, query="Qual a garantia exigida?") is None
    assert cache.get(edital_id=1, query="Qual o prazo de entrega?") is None

    # Clear
    cache.clear()
    assert cache.get(edital_id=1, query="Qual a garantia exigida?") is None
