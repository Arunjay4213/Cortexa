from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_prefix="CORTEX_")

    # API
    port: int = 10000
    admin_secret: str = ""

    # Database
    database_url: str = ""

    # Groq (for decomposition + quote extraction)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # NLI
    nli_model: str = "llama-3.1-8b-instant"
    nli_entailment_threshold: float = 0.7

    # Verification
    max_claims: int = 50
    max_source_chars: int = 50000
