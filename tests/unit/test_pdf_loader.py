from pathlib import Path

import pymupdf
import pytest

from src.db.models import TipoChunk
from src.ingestion.pdf_loader import PDFIngestionPipeline
from src.ingestion.validator import InvalidPDFMagicBytesError


@pytest.fixture
def synthetic_pdf_bytes():
    """Gera um PDF sintético válido em memória com 2 páginas usando PyMuPDF."""
    doc = pymupdf.open()

    # Página 1: Cláusulas do Edital
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text(
        (50, 72),
        "1. DO OBJETO\n"
        "1.1 Contratação de serviços de tecnologia da informação e comunicação.\n"
        "1.2 O prazo de vigência contratual será de 12 (doze) meses.",
        fontsize=11,
    )

    # Página 2: Cláusula de Garantia
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text(
        (50, 72),
        "14. DA GARANTIA CONTRATUAL\n"
        "14.1 A garantia contratual é de 5% do valor total adjudicado.",
        fontsize=11,
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_pdf_ingestion_pipeline_synthetic(synthetic_pdf_bytes):
    """Valida ingestão completa de PDF preservando números de página e tipo de chunk."""
    pipeline = PDFIngestionPipeline()
    result = pipeline.process_file_bytes(synthetic_pdf_bytes, filename="edital_sintetico.pdf")

    assert result.sucesso is True
    assert result.total_paginas == 2
    assert len(result.paginas) == 2

    # Validação da Página 1
    p1 = result.paginas[0]
    assert p1.numero_pagina == 1
    assert p1.tipo == TipoChunk.TEXTO
    assert "1. DO OBJETO" in p1.texto
    assert "1.1 Contratação de serviços" in p1.texto

    # Validação da Página 2
    p2 = result.paginas[1]
    assert p2.numero_pagina == 2
    assert p2.tipo == TipoChunk.TEXTO
    assert "14. DA GARANTIA CONTRATUAL" in p2.texto
    assert "14.1 A garantia contratual é de 5%" in p2.texto


def test_pdf_ingestion_rejects_corrupted():
    """Valida rejeição de bytes corrompidos que não constituem um PDF."""
    pipeline = PDFIngestionPipeline()
    with pytest.raises(InvalidPDFMagicBytesError):
        pipeline.process_file_bytes(b"bad content", "corrompido.pdf")


def test_pdf_ingestion_real_spec_document():
    """Valida extração sobre o documento real de requisitos presente na raiz do projeto."""
    spec_path = Path("Licita-RAG Documento de Requisitos e Especificações.pdf")
    if not spec_path.exists():
        pytest.skip("Documento de especificações não encontrado na raiz.")

    pipeline = PDFIngestionPipeline()
    result = pipeline.process_file_path(spec_path)

    assert result.sucesso is True
    assert result.total_paginas == 17
    assert len(result.paginas) == 17

    # Verifica a primeira página
    p1 = result.paginas[0]
    assert p1.numero_pagina == 1
    assert "Licita-RAG: Documento de Requisitos e" in p1.texto
    assert len(p1.tabelas) >= 1  # Tabela de objetivos mensuráveis (OBJ-01 a OBJ-04)

    # Verifica que as linhas da tabela foram extraídas com repetição de cabeçalho
    table = p1.tabelas[0]
    chunks_tabela = table.to_chunk_texts()
    assert len(chunks_tabela) >= 1
    assert "[Tabela - Pág. 1]" in chunks_tabela[0]
