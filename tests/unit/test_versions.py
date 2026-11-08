from src.chunking.models import ParsedChunk
from src.db.models import TipoDocumento
from src.ingestion.versions import ErrataPrecedenceResolver


def test_errata_precedence_replaces_original_clause_ca08_rn03():
    """Critério CA-08 e Regra RN-03: Errata mais recente prevalece sobre o texto original e sinaliza retificação."""
    chunk_original = ParsedChunk(
        pagina=12,
        item="14.1",
        texto="14.1 O prazo de entrega é de 15 dias corridos.",
        metadados={"versao": 1, "tipo_documento": TipoDocumento.EDITAL, "nome_arquivo": "edital.pdf"},
    )

    chunk_errata = ParsedChunk(
        pagina=2,
        item="14.1",
        texto="14.1 O prazo de entrega fica prorrogado para 30 dias corridos.",
        metadados={"versao": 2, "tipo_documento": TipoDocumento.ERRATA, "nome_arquivo": "errata_01.pdf"},
    )

    resolver = ErrataPrecedenceResolver()
    result = resolver.resolve_precedence([chunk_original, chunk_errata])

    # Apenas o chunk da errata deve permanecer ativo para o item 14.1
    assert len(result.chunks_ativos) == 1
    chunk_vencedor = result.chunks_ativos[0]

    assert "fica prorrogado para 30 dias corridos" in chunk_vencedor.texto
    assert "retificado por Errata v2" in chunk_vencedor.texto
    assert chunk_vencedor.metadados["retificado"] is True

    # O original deve constar na lista de substituídos
    assert len(result.chunks_substituidos) == 1
    assert result.chunks_substituidos[0] == chunk_original

    # O dicionário de itens alterados deve conter o item 14.1
    assert "14.1" in result.itens_alterados


def test_version_resolver_keeps_unique_chunks():
    """Valida que cláusulas sem retificação são preservadas integralmente."""
    c1 = ParsedChunk(pagina=1, item="1.1", texto="Objeto da contratação.", metadados={"versao": 1})
    c2 = ParsedChunk(pagina=2, item="2.1", texto="Condições de participação.", metadados={"versao": 1})

    resolver = ErrataPrecedenceResolver()
    result = resolver.resolve_precedence([c1, c2])

    assert len(result.chunks_ativos) == 2
    assert len(result.chunks_substituidos) == 0
    assert result.itens_alterados == {}
