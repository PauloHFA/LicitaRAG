import io
import logging
from pathlib import Path

import pymupdf

from src.config import settings
from src.db.models import TipoChunk
from src.ingestion.models import ExtractedPage, IngestionResult
from src.ingestion.ocr_fallback import OCRFallbackProcessor, is_page_scanned_or_empty
from src.ingestion.table_extractor import TableExtractor
from src.ingestion.validator import validate_pdf_file

logger = logging.getLogger(__name__)


class PDFIngestionPipeline:
    """Orquestrador do pipeline de ingestão de documentos PDF para o Licita-RAG.

    Executa:
    1. Validação estrita de Magic Bytes e limite de tamanho (RF-02, CA-02).
    2. Extração de texto página a página mantendo a numeração original (RF-04).
    3. Detecção e OCR de páginas escaneadas / imagens (RF-04, CA-07).
    4. Extração de tabelas com repetição de cabeçalho por linha (RF-05, CA-05).
    """

    def __init__(self, max_size_mb: int | None = None) -> None:
        self.max_size_mb = max_size_mb or settings.MAX_FILE_SIZE_MB
        self.table_extractor = TableExtractor()
        self.ocr_processor = OCRFallbackProcessor()

    def process_file_bytes(
        self,
        content: bytes,
        filename: str = "documento.pdf",
    ) -> IngestionResult:
        """Processa um arquivo PDF a partir de seu conteúdo binário (ex: upload multipart)."""
        clean_filename, file_hash = validate_pdf_file(
            content=content,
            filename=filename,
            max_size_mb=self.max_size_mb,
        )

        try:
            doc = pymupdf.open(stream=io.BytesIO(content), filetype="pdf")
            return self._process_doc(doc, clean_filename, file_hash)
        except Exception as e:
            logger.error("Falha ao abrir PDF %s: %s", clean_filename, e)
            return IngestionResult(
                nome_arquivo=clean_filename,
                hash_sha256=file_hash,
                total_paginas=0,
                sucesso=False,
                erros=[f"Falha de leitura do PDF: {e!s}"],
            )

    def process_file_path(self, file_path: str | Path) -> IngestionResult:
        """Processa um arquivo PDF a partir do sistema de arquivos."""
        path = Path(file_path)
        content = path.read_bytes()
        return self.process_file_bytes(content=content, filename=path.name)

    def _process_doc(
        self,
        doc: pymupdf.Document,
        filename: str,
        file_hash: str,
    ) -> IngestionResult:
        """Varre página por página do documento aberto."""
        total_paginas = len(doc)
        paginas_extraidas: list[ExtractedPage] = []
        erros: list[str] = []

        for page_index in range(total_paginas):
            page_num = page_index + 1  # 1-indexed para conferência com o edital físico
            try:
                page = doc[page_index]
                raw_text = page.get_text("text").strip()

                # Verifica se a página é escaneada / vazia de texto
                if is_page_scanned_or_empty(raw_text):
                    logger.debug("Página %d considerada escaneada. Acionando OCR.", page_num)
                    extracted_page = self.ocr_processor.process_scanned_page(page, page_num)
                else:
                    extracted_page = ExtractedPage(
                        numero_pagina=page_num,
                        texto=raw_text,
                        tipo=TipoChunk.TEXTO,
                        confianca=1.0,
                    )

                # Extrai tabelas presentes na página
                tables = self.table_extractor.extract_tables_from_page(page, page_num)
                extracted_page.tabelas = tables

                paginas_extraidas.append(extracted_page)

            except Exception as e:
                msg = f"Erro ao processar página {page_num} do arquivo {filename}: {e!s}"
                logger.error(msg)
                erros.append(msg)

        doc.close()

        return IngestionResult(
            nome_arquivo=filename,
            hash_sha256=file_hash,
            total_paginas=total_paginas,
            paginas=paginas_extraidas,
            sucesso=(len(erros) == 0),
            erros=erros,
        )
