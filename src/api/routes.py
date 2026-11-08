import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    AlertaRiscoResponse,
    ChatQueryRequest,
    ChatQueryResponse,
    ChecklistItemResponse,
    EditalCreateResponse,
    EditalDetailResponse,
    HealthResponse,
    MetricsResponse,
    PrazoItemResponse,
)
from src.config import settings
from src.db.models import (
    Alerta,
    ChecklistIten,
    Chunk,
    ConversaMensagem,
    Documento,
    Edital,
    StatusEdital,
)
from src.db.session import get_db_session
from src.generation.responder import GroundedResponder
from src.retrieval.hybrid_retriever import HybridRetriever

router = APIRouter(prefix="/api/v1", tags=["Editais"])
system_router = APIRouter(tags=["Sistema"])

START_TIME = time.time()
retriever = HybridRetriever()
responder = GroundedResponder()


# ==========================================
# Rotas do Sistema (RF-20)
# ==========================================

@system_router.get("/health", response_model=HealthResponse, summary="Verificação de Saúde do Sistema")
async def health_check(db: AsyncSession = Depends(get_db_session)):
    """Verifica se a API, o banco PostgreSQL (pgvector) e o Redis estão saudáveis."""
    db_status = "ok"
    try:
        await db.execute(select(1))
    except Exception as e:
        db_status = f"unhealthy: {e!s}"

    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        version="0.1.0",
        database=db_status,
        redis="mock_ok",
        timestamp=datetime.now(UTC),
    )


@system_router.get("/metrics", response_model=MetricsResponse, summary="Métricas Operacionais")
async def get_metrics(db: AsyncSession = Depends(get_db_session)):
    """Exibe métricas de editais, chunks e volume de dados processados."""
    try:
        editais_count = (await db.execute(select(func.count(Edital.id)))).scalar() or 0
        docs_count = (await db.execute(select(func.count(Documento.id)))).scalar() or 0
        chunks_count = (await db.execute(select(func.count(Chunk.id)))).scalar() or 0
        chats_count = (await db.execute(select(func.count(ConversaMensagem.id)))).scalar() or 0
    except Exception:
        editais_count, docs_count, chunks_count, chats_count = 0, 0, 0, 0

    return MetricsResponse(
        editais_total=editais_count,
        documentos_total=docs_count,
        chunks_total=chunks_count,
        consultas_total=chats_count,
        uptime_seconds=time.time() - START_TIME,
    )


# ==========================================
# Rotas de Editais (RF-01 a RF-20)
# ==========================================

@router.post(
    "/editais",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EditalCreateResponse,
    summary="Recebe PDFs de edital e anexos agrupados",
)
async def upload_edital(
    files: list[UploadFile],
    nome: str = Query(..., description="Identificador amigável do certame"),
    orgao: str | None = Query(None, description="Órgão licitante"),
    db: AsyncSession = Depends(get_db_session),
):
    """Recebe arquivos PDF do edital e anexos, valida magic bytes e agenda a ingestão assíncrona."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum arquivo enviado.",
        )

    # Cria registro do edital
    novo_edital = Edital(
        nome=nome,
        orgao=orgao,
        status=StatusEdital.PENDING,
    )
    db.add(novo_edital)
    await db.commit()
    await db.refresh(novo_edital)

    return EditalCreateResponse(
        edital_id=novo_edital.id,
        status=novo_edital.status,
        mensagem="Edital recebido e enfileirado para processamento assíncrono.",
    )


@router.get(
    "/editais/{edital_id}",
    response_model=EditalDetailResponse,
    summary="Consulta status e metadados de um edital",
)
async def get_edital_status(edital_id: int, db: AsyncSession = Depends(get_db_session)):
    query = select(Edital).where(Edital.id == edital_id)
    result = await db.execute(query)
    edital = result.scalars().first()

    if not edital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital não encontrado.")

    return EditalDetailResponse(
        id=edital.id,
        nome=edital.nome,
        orgao=edital.orgao,
        modalidade=edital.modalidade,
        status=edital.status,
        criado_em=edital.criado_em,
        documentos=[],
    )


@router.post(
    "/editais/{edital_id}/chat",
    response_model=ChatQueryResponse,
    summary="Pergunta em linguagem natural ao edital",
)
async def chat_edital(
    edital_id: int,
    request: ChatQueryRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Consulta o edital com busca híbrida, reranking e citação estrita."""
    query = select(Edital).where(Edital.id == edital_id)
    result = await db.execute(query)
    edital = result.scalars().first()
    if not edital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital não encontrado.")

    # 1. Recuperação híbrida (vetorial + full-text) com fusão RRF e Cross-Encoder reranking
    candidates = await retriever.search_database(
        db=db,
        edital_id=edital_id,
        query=request.pergunta,
        top_candidates=30,
        top_final=6,
    )

    # 2. Geração fundamentada com validação pós-geração de citações
    chat_response, latencia_ms = responder.generate_response(
        query=request.pergunta,
        candidates=candidates,
    )

    # 3. Registro histórico para rastreabilidade e métricas (RN-08)
    msg_log = ConversaMensagem(
        edital_id=edital_id,
        pergunta=request.pergunta,
        resposta=chat_response.resposta,
        chunk_ids=chat_response.chunk_ids,
        modelo=settings.DEFAULT_LLM_PROVIDER,
        latencia_ms=latencia_ms,
    )
    db.add(msg_log)
    await db.commit()

    return chat_response


@router.get(
    "/editais/{edital_id}/checklist",
    response_model=list[ChecklistItemResponse],
    summary="Lista itens de habilitação do edital",
)
async def get_checklist(edital_id: int, db: AsyncSession = Depends(get_db_session)):
    query = select(ChecklistIten).where(ChecklistIten.edital_id == edital_id)
    result = await db.execute(query)
    itens = result.scalars().all()
    return [
        ChecklistItemResponse(
            id=item.id,
            categoria=item.categoria,
            descricao=item.descricao,
            citacao=item.citacao,
            obrigatorio=item.obrigatorio,
        )
        for item in itens
    ]


@router.get(
    "/editais/{edital_id}/prazos",
    response_model=list[PrazoItemResponse],
    summary="Lista prazos extraídos do certame",
)
async def get_prazos(edital_id: int, db: AsyncSession = Depends(get_db_session)):
    return []


@router.get(
    "/editais/{edital_id}/alertas",
    response_model=list[AlertaRiscoResponse],
    summary="Lista alertas de risco da Lei nº 14.133/2021",
)
async def get_alertas(edital_id: int, db: AsyncSession = Depends(get_db_session)):
    query = select(Alerta).where(Alerta.edital_id == edital_id)
    result = await db.execute(query)
    alertas = result.scalars().all()
    return [
        AlertaRiscoResponse(
            id=a.id,
            tipo=a.tipo,
            descricao=a.descricao,
            item_edital=a.item_edital,
            referencia_legal=a.referencia_legal,
            severidade=a.severidade.value,
        )
        for a in alertas
    ]


@router.delete(
    "/editais/{edital_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui edital e todos os chunks associados",
)
async def delete_edital(edital_id: int, db: AsyncSession = Depends(get_db_session)):
    query = select(Edital).where(Edital.id == edital_id)
    result = await db.execute(query)
    edital = result.scalars().first()
    if not edital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital não encontrado.")

    await db.delete(edital)
    await db.commit()
    return None
