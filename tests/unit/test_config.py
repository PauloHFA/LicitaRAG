from src.config import Settings, settings


def test_default_settings():
    """Valida se as configurações default obedecem aos requisitos do projeto."""
    assert settings.MAX_FILE_SIZE_MB == 50
    assert settings.EMBEDDING_DIM == 384
    assert settings.APP_ENV in ["development", "testing", "production"]
    assert "pgvector" in settings.DATABASE_URL or "postgresql" in settings.DATABASE_URL


def test_custom_settings(monkeypatch):
    """Valida sobrescrita de variáveis via ambiente."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "100")
    custom = Settings()
    assert custom.APP_ENV == "production"
    assert custom.MAX_FILE_SIZE_MB == 100
