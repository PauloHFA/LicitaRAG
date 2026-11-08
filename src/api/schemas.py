from datetime import datetime

from pydantic import BaseModel, Field

from src.db.models import StatusEdital, TipoDocumento


class CitacaoItem(BaseModel):
    documento: str = Field(..., description="Nome ou tipo do documento de origem")
    pagina: int = Field(..., description="Número da página de origem no PDF")
    item: str = Field(..., description="Número da cláusula ou item (ex: 8.4.2)")
    trecho: str = Field(..., description="Trecho literal extraído do documento")


class ChatQueryRequest(BaseModel):
    pergunta: str = Field(..., min_length=2, max_length=1000, description="Pergunta em linguagem natural sobre o edital")


class ChatQueryResponse(BaseModel):
    resposta: str
    citacoes: list[CitacaoItem] = Field(default_factory=list)
    encontrado: bool
    confianca: float = Field(default=0.0, ge=0.0, le=1.0)
    chunk_ids: list[int] = Field(default_factory=list)


class EditalCreateResponse(BaseModel):
    edital_id: int
    status: StatusEdital
    mensagem: str


class DocumentoInfo(BaseModel):
    id: int
    tipo: TipoDocumento
    versao: int
    paginas: int
    status: str


class EditalDetailResponse(BaseModel):
    id: int
    nome: str
    orgao: str | None = None
    modalidade: str | None = None
    status: StatusEdital
    criado_em: datetime
    documentos: list[DocumentoInfo] = Field(default_factory=list)


class ChecklistItemResponse(BaseModel):
    id: int
    categoria: str
    descricao: str
    citacao: str
    obrigatorio: bool


class PrazoItemResponse(BaseModel):
    tipo: str
    data_limite: str
    dias_uteis_ou_corridos: str
    citacao: str


class AlertaRiscoResponse(BaseModel):
    id: int
    tipo: str
    descricao: str
    item_edital: str | None = None
    referencia_legal: str | None = None
    severidade: str


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
    timestamp: datetime


class MetricsResponse(BaseModel):
    editais_total: int
    documentos_total: int
    chunks_total: int
    consultas_total: int
    uptime_seconds: float
