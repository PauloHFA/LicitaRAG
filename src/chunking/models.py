from dataclasses import dataclass, field
from typing import Any

from src.db.models import TipoChunk


@dataclass
class ParsedChunk:
    """Representação em memória de um fragmento de edital com metadados estruturados.

    Atende à Seção 9 (Estratégia de Chunking e Metadados):
    - pagina: número da página real no PDF.
    - item: identificador da cláusula (ex: '8.4.2').
    - secao: hierarquia da seção pai (ex: '8. DA HABILITAÇÃO > 8.4 Qualificação Técnica').
    - tipo: texto, tabela ou ocr.
    - texto: conteúdo do fragmento pronto para embedding e indexação.
    - confianca: 1.0 para nativo, menor para OCR.
    - metadados: dicionário flexível (versão, tipo de documento, etc.).
    """
    pagina: int
    texto: str
    item: str | None = None
    secao: str | None = None
    tipo: TipoChunk = TipoChunk.TEXTO
    confianca: float = 1.0
    documento_id: int | None = None
    metadados: dict[str, Any] = field(default_factory=dict)

    def to_citation_header(self, doc_name: str = "Edital") -> str:
        """Formata o cabeçalho de citação canônico conforme RN-01.

        Exemplo: [Edital, p. 12, item 8.4.2]
        """
        item_str = self.item or "S/N"
        return f"[{doc_name}, p. {self.pagina}, item {item_str}]"
