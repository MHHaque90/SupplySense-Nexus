"""Core configuration for SupplySense Nexus."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "SupplySense Nexus"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-to-a-secure-random-value"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/supplysense"
    DATABASE_URL_TEST: str = "postgresql://postgres:postgres@localhost:5432/supplysense_test"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    OPENAI_API_KEY: str = ""
    AI_PROVIDER: str = "openai"
    AI_MODEL: str = "gpt-4o-mini"

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    ENABLE_AI_ASSISTANT: bool = False
    ENABLE_OPTIMIZATION: bool = False
    ENABLE_SIMULATION: bool = False

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    DATA_SOURCE_PATH: str = "data/"
    SYNTHETIC_DATA_SEED: int = 42

    model_config = ConfigDict(env_file=".env")


settings = Settings()
