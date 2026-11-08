"""Core configuration for SupplySense Nexus."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SupplySense Nexus"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    # Application authenticates via per-user SHA-256 API key digests (no JWTs);
    # SECRET_KEY is reserved for optional future cryptographic extensions.
    SECRET_KEY: str = "change-me-to-a-secure-random-value"

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/supplysense"
    DATABASE_URL_TEST: str = "postgresql+psycopg://postgres:postgres@localhost:5432/supplysense_test"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    OPENAI_API_KEY: str = ""
    AI_PROVIDER: str = "openai"
    AI_MODEL: str = "gpt-4o-mini"
    AI_REQUEST_TIMEOUT_SECONDS: float = 30.0
    AI_MAX_HISTORY_MESSAGES: int = 12
    AI_MAX_TOOL_CALLS_PER_TURN: int = 8

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    ENABLE_AI_ASSISTANT: bool = False
    ENABLE_OPTIMIZATION: bool = False
    ENABLE_SIMULATION: bool = False

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5173",
    ]

    DATA_SOURCE_PATH: str = "data/"
    SYNTHETIC_DATA_SEED: int = 42

    POOL_SIZE: int = 5
    MAX_OVERFLOW: int = 10
    POOL_RECYCLE: int = 1800
    POOL_PRE_PING: bool = True

    model_config = ConfigDict(env_file=".env", extra="allow")


settings = Settings()
