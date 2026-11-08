from src.audit.models import ExtractedDeadline, ExtractedWarranty
from src.audit.risk_detector import RiskDetector
from src.chunking.models import ParsedChunk
from src.db.models import SeveridadeAlerta


def test_risk_detector_short_proposal_deadline_ca10():
    """Critério CA-10: Prazo de apresentação de propostas inferior ao mínimo legal (8 dias) gera alerta."""
    deadlines = [
        ExtractedDeadline(
            tipo="Abertura / Propostas",
            descricao="Prazo para recebimento de propostas fixado em 5 dias úteis.",
            prazo_valor="5 dias úteis",
            dias_uteis_ou_corridos="dias úteis",
            citacao="[Edital 01, p. 4, item 4.1]",
        )
    ]

    detector = RiskDetector()
    alerts = detector.analyze_risks(chunks=[], deadlines=deadlines)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.tipo == "Prazo Curto para Envio de Propostas"
    assert alert.severidade == SeveridadeAlerta.ALTA
    assert "Art. 55" in alert.referencia_legal
    assert alert.item_edital == "4.1"


def test_risk_detector_strict_suggestion_language_rn05_rn07():
    """Regras RN-05 e RN-07: Alerta deve conter rótulo de sugestão e não emitir parecer taxativo de ilegalidade."""
    deadlines = [
        ExtractedDeadline(
            tipo="Impugnação",
            descricao="Prazo de impugnação até 2 dias úteis.",
            prazo_valor="2 dias úteis",
            dias_uteis_ou_corridos="dias úteis",
            citacao="[Edital 01, p. 3, item 3.2]",
        )
    ]

    detector = RiskDetector()
    alerts = detector.analyze_risks(chunks=[], deadlines=deadlines)

    assert len(alerts) == 1
    alert = alerts[0]

    # RN-07: Linguagem de sugestão, sem juízo taxativo
    assert alert.descricao.startswith("Sugestão de Revisão Humana:")
    assert "ilegal" not in alert.descricao.lower()
    assert "possível incompatibilidade" in alert.descricao.lower() or "aparenta ser inferior" in alert.descricao.lower()

    # RN-05: Citação da lei e do item
    assert "Art. 164 da Lei nº 14.133/2021" in alert.referencia_legal
    assert alert.item_edital == "3.2"


def test_risk_detector_excessive_warranty_and_capital():
    """Valida detecção de garantia acima de 10% (Art. 98) e capital social acima de 10% (Art. 67)."""
    warranty = ExtractedWarranty(
        exigida=True,
        percentual_ou_valor="15%",
        prazo_prestacao="10 dias úteis",
        citacao="[Edital 01, p. 30, item 14.1]",
    )

    chunks = [
        ParsedChunk(
            pagina=16,
            item="8.5.3",
            texto="8.5.3 Comprovação de capital social ou patrimônio líquido mínimo de 20% do valor estimado.",
        )
    ]

    detector = RiskDetector()
    alerts = detector.analyze_risks(chunks=chunks, warranty=warranty)

    assert len(alerts) == 2
    tipos = [a.tipo for a in alerts]
    assert "Garantia Contratual Excessiva" in tipos
    assert "Exigência Desproporcional de Patrimônio/Capital" in tipos
