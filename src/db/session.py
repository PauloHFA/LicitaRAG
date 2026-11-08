from collections.abc import AsyncGenerator
from typing import Any

from src.config import settings

try:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    # Engine assíncrona para PostgreSQL + pgvector
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=(settings.LOG_LEVEL == "DEBUG"),
        future=True,
        pool_pre_ping=True,
    )

    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
        """Dependency injection para sessões assíncronas do banco de dados no FastAPI."""
        async with async_session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

except ImportError:  # pragma: no cover
    # Caso greenlet/asyncio não esteja instalado no host (ex: ambiente puro de lint/unidade)
    engine = None  # type: ignore
    async_session_factory = None  # type: ignore

    async def get_db_session() -> AsyncGenerator[Any, None]:  # type: ignore
        yield None
