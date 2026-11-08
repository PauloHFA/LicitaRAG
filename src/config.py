from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais da aplicação carregadas via variáveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Aplicação
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "licita-rag-secret-development-key"

    # Banco de Dados (PostgreSQL + pgvector)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "licitarag"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/licitarag"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/licitarag"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM Provedores
    DEFAULT_LLM_PROVIDER: str = "groq"  # "groq" ou "ollama"
    GROQ_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # Embeddings & Reranker
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    EMBEDDING_DIM: int = 384
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    DEVICE: str = "cpu"

    # Armazenamento e Limites
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = Path("./data/uploads")
    MAX_FILE_SIZE_MB: int = 50


settings = Settings()
