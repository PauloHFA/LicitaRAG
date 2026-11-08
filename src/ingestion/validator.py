import hashlib
import re
from pathlib import Path


class FileValidationError(Exception):
    """Exceção base para erros de validação de arquivos."""
    pass


class InvalidPDFMagicBytesError(FileValidationError):
    """Lançada quando os magic bytes do arquivo não correspondem a um PDF legítimo (%PDF-)."""
    pass


class FileSizeExceededError(FileValidationError):
    """Lançada quando o tamanho do arquivo excede o limite permitido."""
    pass


# Magic bytes padrão do formato PDF (assinatura inicial de 4 bytes)
PDF_MAGIC_BYTES = b"%PDF-"


def sanitize_filename(filename: str) -> str:
    """Sanitiza o nome do arquivo para prevenir path traversal e caracteres inválidos."""
    # Remove qualquer menção a diretórios ou barras
    name = Path(filename).name
    # Remove caracteres não alfanuméricos exceto hífens, underlines e pontos
    clean_name = re.sub(r"[^\w\s.-]", "", name).strip()
    return clean_name or "documento.pdf"


def calculate_sha256(content: bytes) -> str:
    """Calcula o hash SHA-256 do conteúdo binário do arquivo para controle de integridade."""
    hasher = hashlib.sha256()
    hasher.update(content)
    return hasher.hexdigest()


def validate_pdf_file(
    content: bytes,
    filename: str = "documento.pdf",
    max_size_mb: int = 50,
) -> tuple[str, str]:
    """Valida se o conteúdo é um PDF válido, verifica o tamanho e gera o hash SHA-256.

    Atende aos critérios RF-02 e CA-02:
    - Rejeita arquivos falsificados que usam extensão .pdf mas não possuem magic bytes (%PDF-).
    - Valida o limite de tamanho configurado (default: 50 MB).

    Retorna:
        tuple[nome_sanitizado, hash_sha256]
    """
    # 1. Validação de tamanho
    max_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise FileSizeExceededError(
            f"O arquivo {filename} possui {len(content) / (1024 * 1024):.2f} MB, "
            f"excedendo o limite máximo de {max_size_mb} MB."
        )

    # 2. Validação de Magic Bytes (RF-02 / CA-02)
    if not content.startswith(PDF_MAGIC_BYTES):
        raise InvalidPDFMagicBytesError(
            f"O arquivo '{filename}' não é um documento PDF válido. "
            f"Assinatura de magic bytes incompatível."
        )

    clean_filename = sanitize_filename(filename)
    file_hash = calculate_sha256(content)

    return clean_filename, file_hash
