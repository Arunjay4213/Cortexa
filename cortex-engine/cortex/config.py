"""Environment-based settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Postgres
    database_url: str = "postgresql+asyncpg://postgres:cortex@localhost:5432/cortex"
    database_url_sync: str = "postgresql://postgres:cortex@localhost:5432/cortex"

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Token pricing defaults (GPT-4 class)
    default_input_token_cost: float = 0.00001
    default_output_token_cost: float = 0.00003

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    model_config = {"env_prefix": "CORTEX_"}


settings = Settings()
