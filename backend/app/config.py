"""RegLens configuration — secrets only from environment variables.

No real secret is ever committed. GROQ_API_KEY is optional: without it
RegLens runs in EXTRACTIVE mode (answers quote retrieved clauses directly
and label themselves as extractive / no-LLM) and never fakes a generated
answer. JWT_SECRET defaults to a demo value; live deployments must set it.
"""
import logging
import os

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

DEMO_JWT_SECRET = "reglens-demo-secret-change-me-before-live-use"


class Settings(BaseSettings):
    app_name: str = "RegLens"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    database_url: str = "sqlite:///./reglens.db"
    jwt_secret: str = DEMO_JWT_SECRET
    jwt_algorithm: str = "HS256"
    prompt_version: str = "v1.2"
    confidence_threshold: float = 0.65
    faithfulness_threshold: float = 0.20
    retrieval_top_k: int = 8
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    rate_limit_enabled: bool = True
    rate_limit_login_per_minute: int = 10
    rate_limit_ask_per_minute: int = 30
    seed_on_startup: bool = False

    @property
    def demo_mode(self) -> bool:
        return not bool(self.groq_api_key and self.groq_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_postgres(self) -> bool:
        url = (self.database_url or "").strip().lower()
        return url.startswith("postgresql://") or url.startswith("postgres://")

    @property
    def is_sqlite(self) -> bool:
        return (self.database_url or "").strip().lower().startswith("sqlite")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
if settings.jwt_secret == DEMO_JWT_SECRET and not settings.demo_mode:
    raise RuntimeError(
        "JWT_SECRET is the demo default but GROQ_API_KEY is set (live mode). "
        "Refusing to start: set a strong, unique JWT_SECRET."
    )
if settings.jwt_secret == DEMO_JWT_SECRET:
    logger.warning("JWT_SECRET is the demo default — set a strong JWT_SECRET before live use.")
