from src.chunking.clause_splitter import (
    HierarchicalClauseSplitter,
    HierarchyTracker,
)
from src.db.models import TipoChunk
from src.ingestion.models import ExtractedPage, ExtractedTable, IngestionResult


def test_hierarchy_tracker_nesting_and_unwind():
    """Valida o rastreamento hierárquico pai-filho e o fechamento de escopo."""
    tracker = HierarchyTracker()

    # Nível 1: Seção principal
    item1, sec1 = tracker.register_clause("8.", "8. DA HABILITAÇÃO")
    assert item1 == "8"
    assert sec1 == "8. DA HABILITAÇÃO"

    # Nível 2: Subseção
    item2, sec2 = tracker.register_clause("8.4", "8.4 Qualificação Técnica")
    assert item2 == "8.4"
    assert "8. DA HABILITAÇÃO" in sec2
    assert tracker.get_current_section() == "8. DA HABILITAÇÃO > 8.4 Qualificação Técnica"

    # Nível 3: Subitem específico
    item3, sec3 = tracker.register_clause("8.4.2", "8.4.2 Atestados de capacidade técnica")
    assert item3 == "8.4.2"
    assert "8. DA HABILITAÇÃO > 8.4 Qualificação Técnica" in sec3

    # Nível 1: Nova seção principal deve fechar os níveis 2 e 3 anteriores
    item4, sec4 = tracker.register_clause("9.", "9. DOS RECURSOS")
    assert item4 == "9"
    assert "8. DA HABILITAÇÃO" not in sec4
    assert tracker.get_current_section() == "9. DOS RECURSOS"


def test_clause_splitter_page_parsing():
    """Valida a separação de cláusulas de uma página textual."""
    splitter = HierarchicalClauseSplitter()
    tracker = HierarchyTracker()

    texto_pagina = (
        "PREGÃO ELETRÔNICO Nº 05/2026\n"
        "1. DO OBJETO\n"
        "1.1 Contratação de serviços continuados de TI.\n"
        "1.2 O valor estimado da contratação é de R$ 500.000,00.\n"
        "2. DAS CONDIÇÕES DE PARTICIPAÇÃO\n"
        "2.1 Poderão participar deste certame empresas do ramo."
    )

    page = ExtractedPage(
        numero_pagina=1,
        texto=texto_pagina,
        tipo=TipoChunk.TEXTO,
        confianca=1.0,
    )

    chunks = splitter.split_page(page, tracker)

    # Devem existir chunks correspondentes aos itens identificados
    itens = [c.item for c in chunks if c.item is not None]
    assert "1" in itens or "1.1" in itens
    assert "1.2" in itens
    assert "2.1" in itens

    # Verifica o cabeçalho canônico de citação
    item_1_2 = next(c for c in chunks if c.item == "1.2")
    assert item_1_2.to_citation_header("Edital 05") == "[Edital 05, p. 1, item 1.2]"
    assert "valor estimado" in item_1_2.texto


def test_clause_splitter_long_clause_splitting():
    """Valida divisão de cláusula muito longa mantendo a numeração do item."""
    splitter = HierarchicalClauseSplitter(max_chunk_chars=300)
    tracker = HierarchyTracker()

    # Cria texto extenso com 2 parágrafos
    para1 = "Texto longo do primeiro parágrafo " * 10
    para2 = "Outro texto bem longo do segundo parágrafo " * 10
    long_clause_text = f"14.1 {para1}\n\n{para2}"

    page = ExtractedPage(
        numero_pagina=15,
        texto=long_clause_text,
        tipo=TipoChunk.TEXTO,
        confianca=1.0,
    )

    chunks = splitter.split_page(page, tracker)

    # Deve ter dividido em múltiplos chunks mantendo o item 14.1
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.item == "14.1"
        assert chunk.pagina == 15


def test_clause_splitter_includes_tables():
    """Valida inclusão de chunks de tabelas com tipo TABELA."""
    splitter = HierarchicalClauseSplitter()
    tracker = HierarchyTracker()

    table = ExtractedTable(
        pagina=4,
        headers=["Lote", "Item", "Qtd"],
        rows=[["1", "Servidor", "2"]],
    )

    page = ExtractedPage(
        numero_pagina=4,
        texto="10. DOS LOTES\n10.1 Seguem os lotes da licitação:",
        tipo=TipoChunk.TEXTO,
        tabelas=[table],
    )

    chunks = splitter.split_page(page, tracker)

    table_chunks = [c for c in chunks if c.tipo == TipoChunk.TABELA]
    assert len(table_chunks) == 1
    assert "[Tabela - Pág. 4]" in table_chunks[0].texto
    assert "Servidor" in table_chunks[0].texto


def test_split_ingestion_result_full_pipeline():
    """Valida a segmentação completa de um IngestionResult."""
    splitter = HierarchicalClauseSplitter()

    p1 = ExtractedPage(
        numero_pagina=1,
        texto="1. OBJETO\n1.1 Fornecimento de licenças de software.",
    )
    p2 = ExtractedPage(
        numero_pagina=2,
        texto="2. HABILITAÇÃO\n2.1 Prova de regularidade perante a Fazenda Nacional.",
    )

    ingest_result = IngestionResult(
        nome_arquivo="edital_teste.pdf",
        hash_sha256="abc123hash",
        total_paginas=2,
        paginas=[p1, p2],
    )

    all_chunks = splitter.split_ingestion_result(ingest_result, documento_id=10)

    assert len(all_chunks) >= 2
    assert all_chunks[0].documento_id == 10
    assert all_chunks[0].metadados["nome_arquivo"] == "edital_teste.pdf"
