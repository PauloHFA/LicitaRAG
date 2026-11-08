from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router, system_router
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerenciador de ciclo de vida da aplicação (startup e shutdown)."""
    # Garante que o diretório de uploads exista
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Licita-RAG API",
    description="Assistente RAG com citação estrita para extração e auditoria de conformidade de editais públicos.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configuração de CORS para permitir acesso local e Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de Rotas
app.include_router(system_router)
app.include_router(router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "app": "Licita-RAG",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
