import io
import logging
import re
from typing import Any

import pymupdf
from PIL import Image

from src.db.models import TipoChunk
from src.ingestion.models import ExtractedPage

logger = logging.getLogger(__name__)

# Limiar mínimo de caracteres legíveis para considerar que a página possui texto digital
MIN_TEXT_CHARS_THRESHOLD = 50


def is_page_scanned_or_empty(text: str) -> bool:
    """Detecta se uma página é escaneada ou desprovida de camada de texto digital.

    Verifica se a quantidade de caracteres alfanuméricos úteis está abaixo do limiar.
    """
    clean_text = re.sub(r"\s+", "", text)
    alphanumeric_count = len(re.findall(r"\w", clean_text))
    return alphanumeric_count < MIN_TEXT_CHARS_THRESHOLD


class OCRFallbackProcessor:
    """Processador de OCR para páginas digitalizadas sem camada nativa de texto.

    Atende aos critérios RF-04, CA-07 e Lacuna A2:
    - Converte a página em imagem (200 DPI).
    - Aplica OCR com Tesseract (idioma português: 'por').
    - Marca os chunks como tipo 'ocr' com pontuação de confiança reduzida.
    """

    def __init__(self, lang: str = "por") -> None:
        self.lang = lang
        self.tesseract_available = False
        try:
            import pytesseract
            self.pytesseract: Any = pytesseract
            self.tesseract_available = True
        except ImportError:
            logger.warning(
                "pytesseract não está instalado no ambiente host. "
                "O OCR funcionará no container Docker onde as dependências C estão presentes."
            )
            self.pytesseract = None

    def process_scanned_page(
        self,
        page: pymupdf.Page,
        page_num: int,
        dpi: int = 200,
    ) -> ExtractedPage:
        """Renderiza a página como imagem e executa OCR."""
        if not self.tesseract_available or self.pytesseract is None:
            logger.info("OCR ignorado para pág. %d: pytesseract não disponível.", page_num)
            return ExtractedPage(
                numero_pagina=page_num,
                texto="",
                tipo=TipoChunk.OCR,
                confianca=0.50,
            )

        try:
            # 1. Renderiza a página em imagem no PyMuPDF com alta resolução
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_bytes))

            # 2. Executa Tesseract no idioma português
            ocr_text = self.pytesseract.image_to_string(image, lang=self.lang)
            clean_ocr_text = ocr_text.strip()

            return ExtractedPage(
                numero_pagina=page_num,
                texto=clean_ocr_text,
                tipo=TipoChunk.OCR,
                confianca=0.75,  # Confiança menor que texto nativo (1.0), conforme especificação
            )

        except Exception as e:
            logger.error("Erro durante OCR da página %d: %s", page_num, e)
            return ExtractedPage(
                numero_pagina=page_num,
                texto="",
                tipo=TipoChunk.OCR,
                confianca=0.30,
            )
