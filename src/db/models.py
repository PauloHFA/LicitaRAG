import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    # Fallback para ambientes em que pgvector ainda não foi instalado no pip global
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):  # type: ignore
        def __init__(self, dim: int = 384):
            self.dim = dim

        def get_col_spec(self, **kw: Any) -> str:
            return f"vector({self.dim})"


from src.config import settings
from src.db.base import Base


class StatusEdital(enum.StrEnum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"


class TipoDocumento(enum.StrEnum):
    EDITAL = "edital"
    TR = "TR"
    ANEXO = "anexo"
    ERRATA = "errata"


class TipoChunk(enum.StrEnum):
    TEXTO = "texto"
    TABELA = "tabela"
    OCR = "ocr"


class SeveridadeAlerta(enum.StrEnum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class Edital(Base):
    __tablename__ = "editais"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    orgao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    modalidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_abertura: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[StatusEdital] = mapped_column(
        Enum(StatusEdital), default=StatusEdital.PENDING, nullable=False, index=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("status", StatusEdital.PENDING)
        kwargs.setdefault("criado_em", datetime.now(UTC))
        super().__init__(**kwargs)

    # Relacionamentos
    documentos: Mapped[list["Documento"]] = relationship(
        "Documento", back_populates="edital", cascade="all, delete-orphan"
    )
    conversas: Mapped[list["ConversaMensagem"]] = relationship(
        "ConversaMensagem", back_populates="edital", cascade="all, delete-orphan"
    )
    checklist_itens: Mapped[list["ChecklistIten"]] = relationship(
        "ChecklistIten", back_populates="edital", cascade="all, delete-orphan"
    )
    alertas: Mapped[list["Alerta"]] = relationship(
        "Alerta", back_populates="edital", cascade="all, delete-orphan"
    )


class Documento(Base):
    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edital_id: Mapped[int] = mapped_column(ForeignKey("editais.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo: Mapped[TipoDocumento] = mapped_column(Enum(TipoDocumento), default=TipoDocumento.EDITAL, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    caminho: Mapped[str] = mapped_column(String(500), nullable=False)
    paginas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="READY", nullable=False)

    edital: Mapped["Edital"] = relationship("Edital", back_populates="documentos")
    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="documento", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False, index=True)
    pagina: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    item: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    secao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tipo: Mapped[TipoChunk] = mapped_column(Enum(TipoChunk), default=TipoChunk.TEXTO, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)

    # Embedding vetorial e índice full-text
    embedding = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=True)
    tsv = mapped_column(TSVECTOR, nullable=True)
    metadados: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    documento: Mapped["Documento"] = relationship("Documento", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_tsv", "tsv", postgresql_using="gin"),
    )


class ConversaMensagem(Base):
    __tablename__ = "conversas_mensagens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edital_id: Mapped[int] = mapped_column(ForeignKey("editais.id", ondelete="CASCADE"), nullable=False, index=True)
    pergunta: Mapped[str] = mapped_column(Text, nullable=False)
    resposta: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latencia_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avaliacao: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "util", "incorreta"
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    edital: Mapped["Edital"] = relationship("Edital", back_populates="conversas")


class ChecklistIten(Base):
    __tablename__ = "checklist_itens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edital_id: Mapped[int] = mapped_column(ForeignKey("editais.id", ondelete="CASCADE"), nullable=False, index=True)
    categoria: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # Jurídica, Fiscal, Técnica, etc.
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    citacao: Mapped[str] = mapped_column(String(255), nullable=False)
    obrigatorio: Mapped[bool] = mapped_column(nullable=False, default=True)

    edital: Mapped["Edital"] = relationship("Edital", back_populates="checklist_itens")


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    edital_id: Mapped[int] = mapped_column(ForeignKey("editais.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    item_edital: Mapped[str | None] = mapped_column(String(50), nullable=True)
    referencia_legal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severidade: Mapped[SeveridadeAlerta] = mapped_column(
        Enum(SeveridadeAlerta), default=SeveridadeAlerta.MEDIA, nullable=False
    )

    edital: Mapped["Edital"] = relationship("Edital", back_populates="alertas")


class BaseLegal(Base):
    """Índice separado para a Lei nº 14.133/2021 e legislação de apoio."""
    __tablename__ = "base_legal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    norma: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # Ex: "Lei 14.133/2021"
    artigo: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(settings.EMBEDDING_DIM), nullable=True)
    tsv = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (
        Index("idx_base_legal_tsv", "tsv", postgresql_using="gin"),
    )
