import logging
from dataclasses import dataclass

from src.chunking.models import ParsedChunk
from src.db.models import TipoDocumento

logger = logging.getLogger(__name__)


@dataclass
class VersionResolutionResult:
    """Resultado da resolução de precedência entre edital original e adendos/erratas (RN-03, CA-08)."""
    chunks_ativos: list[ParsedChunk]
    chunks_substituidos: list[ParsedChunk]
    itens_alterados: dict[str, str]  # item -> motivo/versão


class ErrataPrecedenceResolver:
    """Gerencia a precedência temporal de erratas sobre o texto original do edital (RN-03, CA-08).

    Regra de negócio:
    - Se uma errata (versão superior) altera uma cláusula ou prazo existente,
      a nova redação prevalece sobre a anterior.
    - A resposta e o chunk retêm a indicação de que o item foi retificado.
    """

    def resolve_precedence(
        self,
        chunks: list[ParsedChunk],
    ) -> VersionResolutionResult:
        """Resolve a precedência entre múltiplos documentos versionados de um mesmo certame."""
        if not chunks:
            return VersionResolutionResult([], [], {})

        # Agrupa chunks por item/cláusula (ex: "14.1", "3.1")
        chunks_by_item: dict[str, list[ParsedChunk]] = {}
        general_chunks: list[ParsedChunk] = []

        for chunk in chunks:
            if chunk.item:
                clean_item = chunk.item.strip().rstrip(".")
                chunks_by_item.setdefault(clean_item, []).append(chunk)
            else:
                general_chunks.append(chunk)

        ativos: list[ParsedChunk] = list(general_chunks)
        substituidos: list[ParsedChunk] = []
        itens_alterados: dict[str, str] = {}

        for item_key, item_chunks in chunks_by_item.items():
            if len(item_chunks) == 1:
                ativos.append(item_chunks[0])
                continue

            # Se houver múltiplos chunks para o mesmo item, ordena pela versão decrescente
            # Metadados esperados: "versao" (int) e "tipo_documento" (TipoDocumento ou str)
            def sort_key(c: ParsedChunk) -> tuple[int, int]:
                versao = int(c.metadados.get("versao", 1))
                tipo_doc = c.metadados.get("tipo_documento", TipoDocumento.EDITAL)
                prioridade_tipo = 2 if tipo_doc in (TipoDocumento.ERRATA, "errata") else 1
                return (versao, prioridade_tipo)

            sorted_chunks = sorted(item_chunks, key=sort_key, reverse=True)
            mais_recente = sorted_chunks[0]
            antigos = sorted_chunks[1:]

            # Anota no chunk vencedor que ele retificou uma versão anterior (RN-03, CA-08)
            versao_recente = mais_recente.metadados.get("versao", 2)
            orig_doc_name = antigos[0].metadados.get("nome_arquivo", "Edital original")

            aviso_retificacao = (
                f"[Item {item_key} retificado por Errata v{versao_recente} - Prevalece sobre {orig_doc_name}] "
            )

            # Evita duplicar prefixo
            if not mais_recente.texto.startswith("[Item"):
                mais_recente.texto = f"{aviso_retificacao}{mais_recente.texto}"

            mais_recente.metadados["retificado"] = True
            mais_recente.metadados["versao_anterior_substituida"] = antigos[0].metadados.get("versao", 1)

            itens_alterados[item_key] = f"Retificado na Errata v{versao_recente}"
            ativos.append(mais_recente)
            substituidos.extend(antigos)

        return VersionResolutionResult(
            chunks_ativos=ativos,
            chunks_substituidos=substituidos,
            itens_alterados=itens_alterados,
        )
