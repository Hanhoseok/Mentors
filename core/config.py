from typing import Literal

from pydantic import field_validator
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

    llm_provider: Literal["openai", "anthropic", "google"] = "google"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None

    # Embedding provider override.
    # 미설정 시 LLM_PROVIDER를 따라간다 (backward compatibility).
    # ⚠️ 변경 시 기존 Chroma collection을 재생성하거나 provider별로 collection 분리 필요
    #    (OpenAI text-embedding-3-small = 1536d, Gemini gemini-embedding-001 = 3072d).
    embedding_provider: Literal["openai", "google"] | None = None

    # chat use_case별 provider override.
    # 미설정 시 코드 디폴트 (content → openai, debate → google).
    # 디폴트 provider의 API 키가 없으면 자동으로 LLM_PROVIDER로 fallback.
    content_llm_provider: Literal["openai", "anthropic", "google"] | None = None
    debate_llm_provider: Literal["openai", "anthropic", "google"] | None = None

    naver_client_id: str | None = None
    naver_client_secret: str | None = None
    llm_stream_timeout_s: int = 60

    chroma_host: str = "localhost"
    chroma_port: int = 8001

    fcm_credentials_path: str | None = None

    scheduler_timezone: str = "Asia/Seoul"
    scheduler_jobstore_url: str | None = None

    @property
    def effective_jobstore_url(self) -> str:
        return self.scheduler_jobstore_url or self.database_url

    # ------------------------------------------------------------------
    # env 값 정규화
    # ------------------------------------------------------------------
    # .env에서 `KEY= value` 처럼 공백이 섞이거나 `KEY=` 처럼 빈값으로 둘 때
    # Pydantic Literal validation이 깨지지 않게 strip + 빈문자열→None 변환.
    # mode="before" 라 타입 검사 전에 동작.

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalize_llm_provider(cls, v):
        """디폴트가 있는 필수 필드 — 공백/빈값이면 디폴트("google")로 fallback.

        (None을 리턴하면 Literal 검증에서 실패하므로 명시적 디폴트 반환)
        """
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return "google"
        return v

    @field_validator(
        "embedding_provider",
        "content_llm_provider",
        "debate_llm_provider",
        mode="before",
    )
    @classmethod
    def _normalize_optional_provider(cls, v):
        """Optional Literal — 빈값/공백은 None으로 정규화."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
        return v


settings = Settings()
