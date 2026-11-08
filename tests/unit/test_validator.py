import pytest

from src.ingestion.validator import (
    FileSizeExceededError,
    InvalidPDFMagicBytesError,
    calculate_sha256,
    sanitize_filename,
    validate_pdf_file,
)


def test_sanitize_filename():
    """Valida proteção contra Directory Traversal e caracteres estranhos."""
    assert sanitize_filename("../../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("..\\..\\malicious.pdf") == "malicious.pdf"
    assert sanitize_filename("edital_pregao_42-2026.pdf") == "edital_pregao_42-2026.pdf"


def test_calculate_sha256():
    """Valida integridade do hash SHA-256."""
    data = b"conteudo de teste para licita-rag"
    expected_hash = "98089ebaca5f2bafec3cdabe05d4f8b9c274718694cfa51ebe6c423b097381e1"
    assert calculate_sha256(data) == expected_hash


def test_validate_valid_pdf_magic_bytes():
    """Valida aceitação de arquivo que inicia com %PDF-."""
    fake_pdf = b"%PDF-1.7\nstream de teste..."
    filename, file_hash = validate_pdf_file(fake_pdf, "edital.pdf", max_size_mb=10)
    assert filename == "edital.pdf"
    assert len(file_hash) == 64


def test_reject_invalid_magic_bytes_ca02():
    """Critério CA-02: Rejeição de arquivo com extensão .pdf mas conteúdo falso."""
    fake_text_file = b"Isso eh apenas um arquivo de texto fingindo ser PDF"
    with pytest.raises(InvalidPDFMagicBytesError) as exc_info:
        validate_pdf_file(fake_text_file, "falso_edital.pdf", max_size_mb=10)
    assert "não é um documento PDF válido" in str(exc_info.value)


def test_reject_oversized_file_rf02():
    """Critério RF-02: Rejeição de arquivos que excedem o tamanho máximo permitido."""
    large_pdf_header = b"%PDF-1.4\n" + (b"A" * (2 * 1024 * 1024))  # 2 MB
    with pytest.raises(FileSizeExceededError) as exc_info:
        validate_pdf_file(large_pdf_header, "grande.pdf", max_size_mb=1)  # Limite 1 MB
    assert "excedendo o limite máximo" in str(exc_info.value)
