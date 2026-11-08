import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.retrieval.embeddings import EmbeddingService
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.rrf import (
    RankedCandidate,
    RRFScoredCandidate,
    reciprocal_rank_fusion,
)

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Motor de busca híbrida (vetorial + textual) com fusão RRF e Cross-Encoder reranking (RF-08, RF-09)."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        reranker: CrossEncoderReranker | None = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.reranker = reranker or CrossEncoderReranker()

    async def search_database(
        self,
        db: AsyncSession,
        edital_id: int,
        query: str,
        top_candidates: int = 30,
        top_final: int = 6,
    ) -> list[RRFScoredCandidate]:
        """Executa a busca híbrida completa contra o banco PostgreSQL + pgvector."""
        # 1. Gera embedding da consulta
        query_vector = self.embedding_service.embed_query(query)
        vector_str = "[" + ",".join(f"{x:.6f}" for x in query_vector) + "]"

        # 2. Busca Vetorial (pgvector cosine similarity: operador <=>)
        vector_sql = text("""
            SELECT c.id, c.texto, c.pagina, c.item, c.secao, c.tipo, c.metadados,
                   (1 - (c.embedding <=> :vector::vector)) AS score
            FROM chunks c
            JOIN documentos d ON c.documento_id = d.id
            WHERE d.edital_id = :edital_id AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> :vector::vector ASC
            LIMIT :limit;
        """)

        # 3. Busca Textual Full-Text (tsvector com dicionário português)
        lexical_sql = text("""
            SELECT c.id, c.texto, c.pagina, c.item, c.secao, c.tipo, c.metadados,
                   ts_rank_cd(c.tsv, plainto_tsquery('portuguese', :query)) AS score
            FROM chunks c
            JOIN documentos d ON c.documento_id = d.id
            WHERE d.edital_id = :edital_id AND c.tsv @@ plainto_tsquery('portuguese', :query)
            ORDER BY score DESC
            LIMIT :limit;
        """)

        try:
            vec_res = await db.execute(
                vector_sql,
                {"vector": vector_str, "edital_id": edital_id, "limit": top_candidates},
            )
            lex_res = await db.execute(
                lexical_sql,
                {"query": query, "edital_id": edital_id, "limit": top_candidates},
            )

            vector_candidates = [
                self._row_to_candidate(row) for row in vec_res.fetchall()
            ]
            lexical_candidates = [
                self._row_to_candidate(row) for row in lex_res.fetchall()
            ]

        except Exception as e:
            logger.error("Erro durante execução de busca híbrida no banco: %s", e)
            return []

        # 4. Fusão RRF dos dois canais
        fused = reciprocal_rank_fusion(
            vector_results=vector_candidates,
            lexical_results=lexical_candidates,
            k=60,
            top_n=top_candidates,
        )

        # 5. Re-ranking final para seleção dos melhores trechos
        reranked = self.reranker.rerank(query=query, candidates=fused, top_k=top_final)
        return reranked

    def search_in_memory(
        self,
        query: str,
        candidates: list[RankedCandidate],
        top_candidates: int = 20,
        top_final: int = 5,
    ) -> list[RRFScoredCandidate]:
        """Executa busca híbrida em memória sobre uma lista de candidatos (útil para testes unitários e benchmarks)."""
        query_vector = self.embedding_service.embed_query(query)

        # Simula ranking vetorial por produto escalar (vetores já são normalizados L2)
        vector_candidates: list[RankedCandidate] = []
        for cand in candidates:
            cand_vec = self.embedding_service.embed_documents([cand.texto])[0]
            # Similaridade cosseno = dot product de vetores unitários
            sim = sum(a * b for a, b in zip(query_vector, cand_vec, strict=False))
            cand_copy = self._clone_candidate(cand, score=sim)
            vector_candidates.append(cand_copy)

        vector_candidates.sort(key=lambda c: c.score_original, reverse=True)
        top_vector = vector_candidates[:top_candidates]

        # Simula ranking lexical por termos coincidentes
        query_words = set(query.lower().split())
        lexical_candidates: list[RankedCandidate] = []
        for cand in candidates:
            cand_words = set(cand.texto.lower().split())
            overlap = len(query_words.intersection(cand_words))
            if overlap > 0:
                cand_copy = self._clone_candidate(cand, score=float(overlap))
                lexical_candidates.append(cand_copy)

        lexical_candidates.sort(key=lambda c: c.score_original, reverse=True)
        top_lexical = lexical_candidates[:top_candidates]

        # Fusão RRF
        fused = reciprocal_rank_fusion(
            vector_results=top_vector,
            lexical_results=top_lexical,
            k=60,
            top_n=top_candidates,
        )

        # Re-ranking
        return self.reranker.rerank(query=query, candidates=fused, top_k=top_final)

    @staticmethod
    def _row_to_candidate(row: Any) -> RankedCandidate:
        return RankedCandidate(
            chunk_id=row[0],
            texto=row[1],
            pagina=row[2],
            item=row[3],
            secao=row[4],
            tipo=str(row[5]),
            metadados=dict(row[6] or {}),
            score_original=float(row[7] or 0.0),
        )

    @staticmethod
    def _clone_candidate(cand: RankedCandidate, score: float) -> RankedCandidate:
        return RankedCandidate(
            chunk_id=cand.chunk_id,
            texto=cand.texto,
            pagina=cand.pagina,
            item=cand.item,
            secao=cand.secao,
            tipo=cand.tipo,
            confianca=cand.confianca,
            documento_id=cand.documento_id,
            score_original=score,
            metadados=dict(cand.metadados),
        )
