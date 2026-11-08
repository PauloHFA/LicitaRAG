from dataclasses import dataclass, field

from src.db.models import TipoChunk


@dataclass
class ExtractedTable:
    """Representação estruturada de uma tabela extraída de uma página do edital."""
    pagina: int
    headers: list[str]
    rows: list[list[str]]

    def to_chunk_texts(self) -> list[str]:
        """Gera representações em texto de cada linha da tabela com o cabeçalho repetido.

        Conforme RF-05 e Lacuna A3: cada linha vira um chunk com o cabeçalho
        correspondente repetido para evitar perda de contexto de itens/quantidades.
        """
        if not self.rows:
            return []

        header_line = " | ".join(h.strip() for h in self.headers if h)
        chunks: list[str] = []

        for row in self.rows:
            # Filtra valores vazios ou nulos
            clean_cells = [str(c).strip().replace("\n", " ") for c in row if c is not None]
            if not any(clean_cells):
                continue
            row_line = " | ".join(clean_cells)
            chunk_text = f"[Tabela - Pág. {self.pagina}] Cabeçalhos: {header_line} | Dados: {row_line}"
            chunks.append(chunk_text)

        return chunks


@dataclass
class ExtractedPage:
    """Conteúdo e metadados extraídos de uma página individual de um edital."""
    numero_pagina: int  # 1-indexed (página real do PDF)
    texto: str
    tipo: TipoChunk = TipoChunk.TEXTO
    confianca: float = 1.0  # 1.0 para texto nativo; menor para OCR
    tabelas: list[ExtractedTable] = field(default_factory=list)


@dataclass
class IngestionResult:
    """Resultado consolidado da extração e validação de um documento PDF."""
    nome_arquivo: str
    hash_sha256: str
    total_paginas: int
    paginas: list[ExtractedPage] = field(default_factory=list)
    sucesso: bool = True
    erros: list[str] = field(default_factory=list)
