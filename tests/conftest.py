import pytest

from src.config import Settings


@pytest.fixture
def mock_settings(monkeypatch):
    """Fixture para isolar configurações de teste."""
    test_settings = Settings(
        APP_ENV="testing",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        DATABASE_URL_SYNC="sqlite:///:memory:",
        REDIS_URL="redis://localhost:6379/1",
        MAX_FILE_SIZE_MB=50,
        EMBEDDING_DIM=384,
    )
    return test_settings
