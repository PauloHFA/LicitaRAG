"""Módulo de ingestão, validação e extração estruturada de documentos PDF."""
from src.ingestion.models import ExtractedPage, ExtractedTable, IngestionResult
from src.ingestion.ocr_fallback import OCRFallbackProcessor, is_page_scanned_or_empty
from src.ingestion.pdf_loader import PDFIngestionPipeline
from src.ingestion.table_extractor import TableExtractor
from src.ingestion.validator import (
    FileSizeExceededError,
    InvalidPDFMagicBytesError,
    calculate_sha256,
    sanitize_filename,
    validate_pdf_file,
)

__all__ = [
    "ExtractedPage",
    "ExtractedTable",
    "IngestionResult",
    "PDFIngestionPipeline",
    "TableExtractor",
    "OCRFallbackProcessor",
    "is_page_scanned_or_empty",
    "validate_pdf_file",
    "calculate_sha256",
    "sanitize_filename",
    "InvalidPDFMagicBytesError",
    "FileSizeExceededError",
]
