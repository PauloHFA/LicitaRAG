from src.audit.deadlines import DeadlinesAndSanctionsExtractor
from src.chunking.models import ParsedChunk


def test_deadlines_normalization_business_vs_calendar_days_rn06():
    """Regra RN-06: Normalização de prazos distinguindo dias úteis e dias corridos."""
    chunks = [
        ParsedChunk(
            pagina=5,
            item="3.1",
            texto="3.1 Qualquer pessoa poderá impugnar o edital até 3 (três) dias úteis antes da abertura da sessão.",
        ),
        ParsedChunk(
            pagina=5,
            item="3.2",
            texto="3.2 Os pedidos de esclarecimentos deverão ser enviados em até 3 dias úteis.",
        ),
        ParsedChunk(
            pagina=20,
            item="11.4",
            texto="11.4 O prazo de validade das propostas será de 60 (sessenta) dias corridos.",
        ),
        ParsedChunk(
            pagina=30,
            item="18.2",
            texto="18.2 O prazo de entrega definitiva dos bens será de 30 dias contados da ordem de serviço.",
        ),
    ]

    extractor = DeadlinesAndSanctionsExtractor()
    deadlines = extractor.extract_deadlines(chunks, document_name="Edital 01")

    assert len(deadlines) >= 3

    # Impugnação: dias úteis
    impugnacao = next(d for d in deadlines if d.tipo == "Impugnação")
    assert impugnacao.dias_uteis_ou_corridos == "dias úteis"
    assert "3" in impugnacao.prazo_valor
    assert "[Edital 01, p. 5, item 3.1]" == impugnacao.citacao

    # Validade das propostas: dias corridos
    validade = next(d for d in deadlines if d.tipo == "Validade da Proposta")
    assert validade.dias_uteis_ou_corridos == "dias corridos"
    assert "60" in validade.prazo_valor
    assert "[Edital 01, p. 20, item 11.4]" == validade.citacao


def test_warranty_extraction():
    """Valida extração da garantia contratual (RF-14)."""
    chunk = ParsedChunk(
        pagina=45,
        item="14.1",
        texto="14.1 O adjudicatário prestará garantia contratual correspondente a 5% (cinco por cento) do valor total, no prazo de 10 dias úteis.",
    )

    extractor = DeadlinesAndSanctionsExtractor()
    warranty = extractor.extract_warranty([chunk], document_name="Edital 01")

    assert warranty is not None
    assert warranty.exigida is True
    assert "5%" in warranty.percentual_ou_valor
    assert "10 dias úteis" in warranty.prazo_prestacao
    assert "[Edital 01, p. 45, item 14.1]" == warranty.citacao


def test_penalties_extraction():
    """Valida extração das sanções administrativas e multas contratuais (RF-14)."""
    chunks = [
        ParsedChunk(
            pagina=48,
            item="19.1",
            texto="19.1 Pelo atraso injustificado na execução do objeto, a contratada estará sujeita à multa moratória de 0,5% por dia.",
        ),
        ParsedChunk(
            pagina=48,
            item="19.2",
            texto="19.2 Em caso de inexecução total, será aplicada declaração de inidoneidade para licitar.",
        ),
    ]

    extractor = DeadlinesAndSanctionsExtractor()
    penalties = extractor.extract_penalties(chunks, document_name="Edital 01")

    assert len(penalties) >= 2
    tipos = [p.tipo for p in penalties]
    assert "Multa Moratória" in tipos
    assert "Declaração de Inidoneidade" in tipos
