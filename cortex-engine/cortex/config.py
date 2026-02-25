"""Environment-based settings via pydantic-settings."""

import os

# Prevent transformers from importing TensorFlow (only relevant with local models)
os.environ.setdefault("USE_TF", "0")

from pydantic import model_validator
from pydantic_settings import BaseSettings


def _fix_database_url(url: str) -> str:
    """Railway gives postgres:// but SQLAlchemy needs postgresql+asyncpg://."""
    url = url.replace("postgres://", "postgresql://", 1)
    if "postgresql://" in url and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    # Postgres
    database_url: str = "postgresql+asyncpg://postgres@localhost:5432/cortex"
    database_url_sync: str = "postgresql://postgres@localhost:5432/cortex"

    @model_validator(mode="before")
    @classmethod
    def _read_railway_database_url(cls, values: dict) -> dict:
        """Railway sets DATABASE_URL (no prefix). Read it if CORTEX_DATABASE_URL isn't set."""
        raw = os.environ.get("DATABASE_URL", "")
        if raw and not os.environ.get("CORTEX_DATABASE_URL"):
            values["database_url"] = _fix_database_url(raw)
            # Sync URL: strip +asyncpg
            sync = raw.replace("postgres://", "postgresql://", 1)
            values["database_url_sync"] = sync
        return values

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 1536

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Token pricing defaults (GPT-4 class)
    default_input_token_cost: float = 0.00001
    default_output_token_cost: float = 0.00003

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ContextCite (slow-path attribution)
    llm_provider: str = "local"
    llm_api_key: str = ""
    contextcite_num_samples: int = 64
    contextcite_lasso_lambda: float = 0.1

    # CAMA (Claim-Aware Memory Attribution)
    cama_similarity_threshold: float = 0.3
    cama_entailment_threshold: float = 0.5
    cama_hallucination_threshold: float = 0.5
    cama_max_candidates_per_claim: int = 5
    cama_nli_model: str = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
    cama_max_claims: int = 20
    cama_shapley_value_fn: str = "weighted"
    cama_llm_model: str = "gpt-4o-mini"

    # API-based model keys (used when USE_LOCAL_MODELS=false)
    groq_api_key: str = ""
    openai_api_key: str = ""
    use_local_models: bool = False

    # Auth
    admin_secret: str = ""

    model_config = {"env_prefix": "CORTEX_"}


settings = Settings()

# Startup validation: admin secret must be set
if not settings.admin_secret or settings.admin_secret in ("changeme", "changeme-set-CORTEX_ADMIN_SECRET"):
    import warnings
    warnings.warn(
        "CORTEX_ADMIN_SECRET is not set or uses a default value. "
        "Set CORTEX_ADMIN_SECRET environment variable to a secure random string. "
        "API key operations will fail until this is configured.",
        stacklevel=1,
    )

