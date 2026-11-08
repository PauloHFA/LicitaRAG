import re
from typing import Any

from src.chunking.models import ParsedChunk
from src.db.models import TipoChunk
from src.ingestion.models import ExtractedPage, IngestionResult

# Regex para detectar início de cláusula numerada (ex: "1.", "1.1", "8.4.2", "14.1.3.")
CLAUSE_REGEX = re.compile(r"^\s*(\d+(?:\.\d+)*\.?)\s+(.*)", re.DOTALL)


class HierarchyTracker:
    """Rastreia a hierarquia de seções e cláusulas de um edital jurídico."""

    def __init__(self) -> None:
        # Mapeia nível (1, 2, 3...) para (item_normalizado, título_secao)
        self.levels: dict[int, tuple[str, str]] = {}

    @staticmethod
    def _compute_level(item_str: str) -> int:
        """Determina o nível hierárquico com base na contagem de números separados por ponto."""
        cleaned = item_str.strip().rstrip(".")
        parts = cleaned.split(".")
        return len(parts)

    def register_clause(self, raw_item: str, text: str) -> tuple[str, str]:
        """Registra uma nova cláusula, atualiza a árvore e retorna (item_normalizado, caminho_hierarquico)."""
        clean_item = raw_item.strip().rstrip(".")
        level = self._compute_level(clean_item)

        # Extrai o título ou a primeira linha do item
        first_line = text.strip().split("\n")[0][:80].strip()
        title = f"{clean_item}. {first_line}" if not first_line.startswith(clean_item) else first_line

        # Remove níveis inferiores ou iguais que já foram fechados
        keys_to_remove = [k for k in self.levels if k >= level]
        for k in keys_to_remove:
            del self.levels[k]

        # Constrói o caminho dos pais (ancestrais de nível < level)
        parent_titles = [
            self.levels[k][1]
            for k in sorted(self.levels.keys())
            if k < level
        ]

        # Registra o nível atual
        self.levels[level] = (clean_item, title)

        # Monta a string de seção representativa
        if parent_titles:
            secao_path = " > ".join(parent_titles)
        else:
            secao_path = title

        return clean_item, secao_path

    def get_current_section(self) -> str | None:
        """Retorna o caminho da seção atual mais recente."""
        if not self.levels:
            return None
        return " > ".join(self.levels[k][1] for k in sorted(self.levels.keys()))


class HierarchicalClauseSplitter:
    """Segmentador de texto de editais baseado em cláusulas e hierarquia (RF-06).

    Preserva a estrutura lógica de artigos e itens e evita cortar regras jurídicas ao meio.
    """

    def __init__(
        self,
        max_chunk_chars: int = 1200,
        chunk_overlap_chars: int = 150,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.chunk_overlap_chars = chunk_overlap_chars

    def split_page(
        self,
        page: ExtractedPage,
        tracker: HierarchyTracker,
        documento_id: int | None = None,
        metadados_base: dict[str, Any] | None = None,
    ) -> list[ParsedChunk]:
        """Segmenta o texto de uma página individual em chunks hierárquicos."""
        chunks: list[ParsedChunk] = []
        meta = dict(metadados_base or {})
        lines = page.texto.splitlines()

        current_item: str | None = None
        current_section: str | None = tracker.get_current_section()
        current_buffer: list[str] = []

        def flush_buffer() -> None:
            nonlocal current_buffer, current_item, current_section
            if not current_buffer:
                return

            full_text = "\n".join(current_buffer).strip()
            if not full_text:
                current_buffer = []
                return

            # Se o bloco for muito longo, quebra por parágrafos repetindo o número do item
            if len(full_text) > self.max_chunk_chars:
                subchunks = self._split_long_clause(full_text, current_item)
                for sub in subchunks:
                    chunks.append(
                        ParsedChunk(
                            pagina=page.numero_pagina,
                            texto=sub,
                            item=current_item,
                            secao=current_section,
                            tipo=page.tipo,
                            confianca=page.confianca,
                            documento_id=documento_id,
                            metadados=dict(meta),
                        )
                    )
            else:
                chunks.append(
                    ParsedChunk(
                        pagina=page.numero_pagina,
                        texto=full_text,
                        item=current_item,
                        secao=current_section,
                        tipo=page.tipo,
                        confianca=page.confianca,
                        documento_id=documento_id,
                        metadados=dict(meta),
                    )
                )

            current_buffer = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            match = CLAUSE_REGEX.match(line_str)
            if match:
                # Encontrou nova cláusula numerada: descarrega buffer anterior
                flush_buffer()
                raw_item = match.group(1)
                current_item, current_section = tracker.register_clause(raw_item, line_str)
                current_buffer.append(line_str)
            else:
                current_buffer.append(line_str)

        # Descarrega o restante
        flush_buffer()

        # Incorpora chunks provenientes de tabelas estruturadas da página (RF-05)
        for table in page.tabelas:
            for table_chunk_text in table.to_chunk_texts():
                chunks.append(
                    ParsedChunk(
                        pagina=page.numero_pagina,
                        texto=table_chunk_text,
                        item=f"Tabela p.{page.numero_pagina}",
                        secao=current_section,
                        tipo=TipoChunk.TABELA,
                        confianca=page.confianca,
                        documento_id=documento_id,
                        metadados=dict(meta),
                    )
                )

        return chunks

    def _split_long_clause(self, text: str, item: str | None) -> list[str]:
        """Divide uma cláusula excessivamente longa mantendo a numeração do item em cada parte."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) <= 1:
            # Quebra por parágrafos simples ou linhas
            paragraphs = [p.strip() for p in text.splitlines() if p.strip()]

        result_chunks: list[str] = []
        current_chunk_parts: list[str] = []
        current_length = 0
        part_idx = 1

        for para in paragraphs:
            para_len = len(para)
            if current_length + para_len > self.max_chunk_chars and current_chunk_parts:
                combined = " ".join(current_chunk_parts)
                header = f"[Item {item} (parte {part_idx})]" if item else f"[Parte {part_idx}]"
                result_chunks.append(f"{header} {combined}")
                part_idx += 1
                current_chunk_parts = [para]
                current_length = para_len
            else:
                current_chunk_parts.append(para)
                current_length += para_len

        if current_chunk_parts:
            combined = " ".join(current_chunk_parts)
            header = f"[Item {item} (parte {part_idx})]" if (item and part_idx > 1) else ""
            final_text = f"{header} {combined}".strip()
            result_chunks.append(final_text)

        return result_chunks or [text]

    def split_ingestion_result(
        self,
        ingestion_result: IngestionResult,
        documento_id: int | None = None,
        metadados_base: dict[str, Any] | None = None,
    ) -> list[ParsedChunk]:
        """Processa todas as páginas de um IngestionResult produzindo a lista consolidada de chunks."""
        tracker = HierarchyTracker()
        all_chunks: list[ParsedChunk] = []

        base_meta = dict(metadados_base or {})
        base_meta.update({
            "nome_arquivo": ingestion_result.nome_arquivo,
            "hash_sha256": ingestion_result.hash_sha256,
        })

        for page in ingestion_result.paginas:
            page_chunks = self.split_page(
                page=page,
                tracker=tracker,
                documento_id=documento_id,
                metadados_base=base_meta,
            )
            all_chunks.extend(page_chunks)

        return all_chunks
