from src.audit.checklist import ChecklistExtractor
from src.audit.models import CategoriaHabilitacao
from src.chunking.models import ParsedChunk


def test_checklist_extractor_four_categories_ca09():
    """Critério CA-09: Extração de documentos cobrindo as 4 categorias de habilitação com citação."""
    chunks = [
        ParsedChunk(
            pagina=10,
            item="8.2.1",
            secao="8. DA HABILITAÇÃO JURÍDICA",
            texto="8.2.1 Apresentação do contrato social em vigor registrado na Junta Comercial.",
        ),
        ParsedChunk(
            pagina=11,
            item="8.3.1",
            secao="8. REGULARIDADE FISCAL E TRABALHISTA",
            texto="8.3.1 Prova de regularidade perante o FGTS (CRF) e Certidão Negativa de Débitos Trabalhistas (CNDT).",
        ),
        ParsedChunk(
            pagina=12,
            item="8.4.2",
            secao="8. QUALIFICAÇÃO TÉCNICA",
            texto="8.4.2 Atestados de capacidade técnica fornecidos por pessoa jurídica de direito público ou privado.",
        ),
        ParsedChunk(
            pagina=14,
            item="8.5.1",
            secao="8. QUALIFICAÇÃO ECONÔMICO-FINANCEIRA",
            texto="8.5.1 Balanço patrimonial do último exercício e certidão negativa de falência ou recuperação judicial.",
        ),
    ]

    extractor = ChecklistExtractor()
    items = extractor.extract_from_chunks(chunks, document_name="Edital 42")

    assert len(items) >= 4

    categorias_encontradas = {i.categoria for i in items}
    assert CategoriaHabilitacao.JURIDICA.value in categorias_encontradas
    assert CategoriaHabilitacao.FISCAL_TRABALHISTA.value in categorias_encontradas
    assert CategoriaHabilitacao.TECNICA.value in categorias_encontradas
    assert CategoriaHabilitacao.ECONOMICA.value in categorias_encontradas

    # Validação da citação estrita de cada item (CA-09)
    for it in items:
        assert "[Edital 42, p." in it.citacao
        assert "item 8." in it.citacao
        assert it.obrigatorio is True


def test_checklist_clean_descriptions():
    """Valida formatação limpa das descrições do checklist."""
    chunk = ParsedChunk(
        pagina=8,
        item="8.1",
        secao="8. Habilitação",
        texto="a) Ato constitutivo, estatuto ou contrato social consolidado.",
    )

    extractor = ChecklistExtractor()
    items = extractor.extract_from_chunks([chunk])

    assert len(items) == 1
    # Deve ter removido a alínea 'a) '
    assert items[0].descricao.startswith("Ato constitutivo")
    assert items[0].categoria == CategoriaHabilitacao.JURIDICA.value
