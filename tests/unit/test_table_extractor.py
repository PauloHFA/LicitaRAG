from src.ingestion.models import ExtractedTable


def test_table_to_chunk_texts_repetition_of_headers_rf05_ca05():
    """Critério RF-05 e CA-05: Cabeçalho da tabela deve ser repetido em cada linha."""
    table = ExtractedTable(
        pagina=18,
        headers=["Lote", "Item", "Descrição", "Potência Mínima", "Quantidade"],
        rows=[
            ["1", "1", "Servidor de Aplicação", "500W", "4"],
            ["2", "1", "Servidor de Banco de Dados", "750W", "2"],
        ],
    )

    chunks = table.to_chunk_texts()
    assert len(chunks) == 2

    # Verifica a presença do cabeçalho completo repetido na primeira linha
    assert "[Tabela - Pág. 18]" in chunks[0]
    assert "Cabeçalhos: Lote | Item | Descrição | Potência Mínima | Quantidade" in chunks[0]
    assert "Dados: 1 | 1 | Servidor de Aplicação | 500W | 4" in chunks[0]

    # Verifica a segunda linha
    assert "[Tabela - Pág. 18]" in chunks[1]
    assert "Cabeçalhos: Lote | Item | Descrição | Potência Mínima | Quantidade" in chunks[1]
    assert "Dados: 2 | 1 | Servidor de Banco de Dados | 750W | 2" in chunks[1]


def test_table_empty_rows_filtered():
    """Valida descarte de linhas sem dados ou com valores None/vazios."""
    table = ExtractedTable(
        pagina=5,
        headers=["Coluna A", "Coluna B"],
        rows=[
            ["", "   "],
            [None, None],
            ["Valor A", "Valor B"],
        ],
    )

    chunks = table.to_chunk_texts()
    assert len(chunks) == 1
    assert "Dados: Valor A | Valor B" in chunks[0]
