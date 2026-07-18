from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LifeLink FastAPI Service"
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 3010

    postgres_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lifelink_db"
    jwt_secret: str = "change_me"
    privacy_salt: str = "change_me"

    frontend_url: str = "http://localhost:5000"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com"
    groq_model: str = "groq/compound"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    rag_collection: str = "knowledge_chunks"
    rag_vector_index: str = "lifelink_vector_index"
    rag_top_k: int = 5

    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@lifelink.ai"


    @property
    def cors_origins(self) -> list[str]:
        # Keep behavior close to existing Express setup.
        if self.app_env == "production":
            origins = [o.strip().rstrip("/") for o in self.frontend_url.split(",") if o.strip()]
            return origins or ["*"]
        return [
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
