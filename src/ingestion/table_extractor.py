import logging
from typing import Any

import pymupdf

from src.ingestion.models import ExtractedTable

logger = logging.getLogger(__name__)


class TableExtractor:
    """Extrai tabelas de páginas de PDF preservando cabeçalhos e estrutura de linhas."""

    def __init__(self) -> None:
        self.use_pdfplumber = False
        try:
            import pdfplumber  # noqa: F401
            self.use_pdfplumber = True
        except ImportError:
            logger.info("pdfplumber não encontrado. Usando extração nativa de tabelas do PyMuPDF.")

    def extract_tables_from_page(
        self,
        page: pymupdf.Page,
        page_num: int,
    ) -> list[ExtractedTable]:
        """Extrai tabelas de uma página do PyMuPDF.

        Utiliza o motor de tabelas do PyMuPDF (ou pdfplumber se configurado),
        normalizando os cabeçalhos e células.
        """
        extracted_tables: list[ExtractedTable] = []

        try:
            # PyMuPDF 2.0 possui o método nativo find_tables()
            table_finder = page.find_tables()
            if not table_finder.tables:
                return []

            for tab in table_finder.tables:
                raw_data: list[list[Any]] = tab.extract()
                if not raw_data or len(raw_data) < 2:
                    continue  # Requer ao menos cabeçalho + 1 linha de dados

                # Normalização de cabeçalhos
                headers = [
                    str(col).strip().replace("\n", " ") if col is not None else ""
                    for col in raw_data[0]
                ]

                # Normalização das linhas
                rows: list[list[str]] = []
                for row_data in raw_data[1:]:
                    row_cells = [
                        str(cell).strip().replace("\n", " ") if cell is not None else ""
                        for cell in row_data
                    ]
                    # Adiciona somente se houver algum conteúdo
                    if any(row_cells):
                        rows.append(row_cells)

                if rows:
                    extracted_tables.append(
                        ExtractedTable(
                            pagina=page_num,
                            headers=headers,
                            rows=rows,
                        )
                    )

        except Exception as e:
            logger.warning("Falha ao extrair tabelas da página %d: %s", page_num, e)

        return extracted_tables
