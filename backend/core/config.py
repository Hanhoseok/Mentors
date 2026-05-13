from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["dev", "prod"] = "dev"

    database_url: str

    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llm_stream_timeout_s: int = 60

    chroma_host: str = "localhost"
    chroma_port: int = 8001

    fcm_credentials_path: str | None = None

    scheduler_timezone: str = "Asia/Seoul"
    scheduler_jobstore_url: str | None = None

    @property
    def effective_jobstore_url(self) -> str:
        return self.scheduler_jobstore_url or self.database_url


settings = Settings()
