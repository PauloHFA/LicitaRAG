from src.db.models import TipoChunk
from src.ingestion.ocr_fallback import (
    OCRFallbackProcessor,
    is_page_scanned_or_empty,
)


def test_is_page_scanned_or_empty():
    """Valida detecção de páginas escaneadas vs páginas com texto suficiente."""
    # Menos de 50 caracteres alfanuméricos => considerada escaneada/vazia
    assert is_page_scanned_or_empty("") is True
    assert is_page_scanned_or_empty("    \n \t ") is True
    assert is_page_scanned_or_empty("Página 12") is True  # Apenas 8 letras

    # Texto suficiente de um parágrafo normal de edital
    texto_edital = (
        "14.1 A garantia contratual deverá ser prestada no valor correspondente a 5% "
        "(cinco por cento) do valor total adjudicado, no prazo improrrogável de 10 dias úteis."
    )
    assert is_page_scanned_or_empty(texto_edital) is False


def test_ocr_fallback_processor_marking_ca07():
    """Critério CA-07: Processamento de página marcada como OCR deve possuir tipo OCR e confiança menor."""
    processor = OCRFallbackProcessor()
    # Em ambiente sem pytesseract, process_scanned_page retorna ExtractedPage com tipo OCR e confiança menor
    page_result = processor.process_scanned_page(None, page_num=3)  # type: ignore

    assert page_result.numero_pagina == 3
    assert page_result.tipo == TipoChunk.OCR
    assert page_result.confianca < 1.0
