"""LLM 호출 정책 레이어.

client.py는 provider별 실제 API 호출만 담당하고, 이 모듈은 provider/model 선택,
fallback, response_format 같은 공통 호출 정책을 담당한다.

use_case 라우팅 (chat 전용):
  - "content"  → OpenAI         (뉴스 수집 → 번역/요약/키워드)
  - "debate"   → Google Gemini  (멘토 토론)

settings.llm_provider 디폴트는 "google"이라 use_case="debate"는 실질적으로
backward-compat. use_case="content"만 명시적으로 OpenAI로 가게 만들어둠.

해석 우선순위 (chat):
  1. 명시적 `provider=` 인자 (fallback 없음 — 실패 시 그대로 에러)
  2. env override: `settings.{use_case}_llm_provider` (예: DEBATE_LLM_PROVIDER)
  3. `_USE_CASE_ROUTES[use_case]` 기본값
  4. (위 2/3로 결정된 provider의 API 키가 없으면) `settings.llm_provider`로 fallback
  5. use_case도 provider도 없으면 `settings.llm_provider`

⚠️  embed()는 별도 정책 (client._resolve_embedding_provider 참고).
    embedding provider는 vector dimension과 직결되므로 자동 fallback / 강제
    default를 두지 않는다. dev/local에서 collection 만들 때 provider만 명시.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Literal

from core.config import settings
from core.exceptions import ExternalServiceError

from .client import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_CHAT_MODEL,
    LLMClient,
    llm_client,
)
from .dto import ChatResponse, Message, StreamChunk

logger = logging.getLogger("llm")

DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash-lite"

# chat use_case → (provider, default_model)
# embed는 의도적으로 이 매핑에서 제외 (vector dimension 안전성)
_USE_CASE_ROUTES: dict[str, tuple[str, str | None]] = {
    "content": ("openai", DEFAULT_OPENAI_CHAT_MODEL),
    "debate": ("google", DEFAULT_GEMINI_MODEL),
}

# provider → settings.* attribute (API 키 존재 확인용)
_PROVIDER_KEY_ATTRS: dict[str, str] = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "google": "gemini_api_key",
}


class LLMGateway:
    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or llm_client

    @property
    def configured(self) -> bool:
        return self._client.configured

    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: str | None = None,
        provider: str | None = None,
        use_case: str | None = None,
    ) -> ChatResponse:
        selected_provider, selected_model = self._resolve_route(provider, model, use_case)
        try:
            return await self._client.chat(
                messages,
                model=selected_model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                provider=selected_provider,
            )
        except ExternalServiceError as error:
            if not _should_retry_with_gemini_fallback(selected_provider, selected_model, error):
                raise
            logger.info(
                "llm_gateway.google_high_demand_retry",
                extra={
                    "model": selected_model,
                    "fallback_model": DEFAULT_GEMINI_FALLBACK_MODEL,
                },
            )
            return await self._client.chat(
                messages,
                model=DEFAULT_GEMINI_FALLBACK_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                provider=selected_provider,
            )

    async def chat_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        provider: str | None = None,
        use_case: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        selected_provider, selected_model = self._resolve_route(provider, model, use_case)
        try:
            async for chunk in self._client.chat_stream(
                messages,
                model=selected_model,
                temperature=temperature,
                max_tokens=max_tokens,
                provider=selected_provider,
            ):
                yield chunk
        except ExternalServiceError as error:
            if not _should_retry_with_gemini_fallback(selected_provider, selected_model, error):
                raise
            logger.info(
                "llm_gateway.google_stream_high_demand_retry",
                extra={
                    "model": selected_model,
                    "fallback_model": DEFAULT_GEMINI_FALLBACK_MODEL,
                },
            )
            async for chunk in self._client.chat_stream(
                messages,
                model=DEFAULT_GEMINI_FALLBACK_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                provider=selected_provider,
            ):
                yield chunk

    async def embed(
        self,
        text: str,
        provider: Literal["openai", "google"] | None = None,
    ) -> list[float]:
        """벡터 임베딩 — 정책 없이 client로 위임.

        provider 선택 우선순위는 ``client._resolve_embedding_provider``에서 일괄
        관리한다 (1. 인자 → 2. EMBEDDING_PROVIDER → 3. LLM_PROVIDER).

        ⚠️  자동 fallback 없음. embedding provider는 vector dimension과 직결되므로
            지정된 provider가 사용 불가하면 명시적 ExternalServiceError를 던진다.
        """
        return await self._client.embed(text, provider=provider)

    # ------------------------------------------------------------------
    # 내부 라우팅 (chat 전용)
    # ------------------------------------------------------------------

    def _resolve_route(
        self,
        provider: str | None,
        model: str | None,
        use_case: str | None,
    ) -> tuple[str, str | None]:
        """chat provider/model 결정.

        - 명시적 ``provider=``는 fallback 없음 (caller가 의도한 그대로 호출)
        - use_case는 env override → 매핑 → 사용 불가 시 settings.llm_provider로 fallback
        """
        # 1. 명시적 provider 인자가 최우선 (fallback 없음)
        if provider is not None:
            return provider, model or _default_chat_model(provider)

        # 2. use_case 라우팅
        if use_case is not None:
            target_provider, target_default_model = _resolve_use_case_target(use_case)

            if target_provider is not None and _provider_configured(target_provider):
                return (
                    target_provider,
                    model or target_default_model or _default_chat_model(target_provider),
                )

            # use_case 대상 provider 사용 불가 → settings.llm_provider로 fallback
            fallback_provider = settings.llm_provider
            logger.info(
                "llm_gateway.use_case_provider_unavailable_fallback",
                extra={
                    "use_case": use_case,
                    "requested_provider": target_provider,
                    "fallback_provider": fallback_provider,
                    "reason": "api_key_missing_or_unknown_use_case",
                },
            )
            return fallback_provider, model or _default_chat_model(fallback_provider)

        # 3. use_case도 provider도 없으면 글로벌 디폴트
        fallback_provider = settings.llm_provider
        return fallback_provider, model or _default_chat_model(fallback_provider)


# ----------------------------------------------------------------------
# 모듈 함수 — 단위 테스트가 settings monkeypatch만으로 검증할 수 있게 분리
# ----------------------------------------------------------------------


def _resolve_use_case_target(use_case: str) -> tuple[str | None, str | None]:
    """use_case → (target_provider, default_model).

    1순위: env override (settings.{use_case}_llm_provider — 예: DEBATE_LLM_PROVIDER)
    2순위: _USE_CASE_ROUTES 매핑

    env override 값이 들어오면 default_model은 None을 반환해서
    `_default_chat_model(provider)`이 알아서 잡게 한다.

    알 수 없는 use_case면 (None, None) 반환 → caller가 fallback 처리.
    """
    env_attr = f"{use_case}_llm_provider"
    env_override = getattr(settings, env_attr, None)
    if env_override:
        return env_override, None

    route = _USE_CASE_ROUTES.get(use_case)
    if route is None:
        return None, None
    return route


def _provider_configured(provider: str) -> bool:
    """provider의 API 키가 settings에 있는지 검사. 모르는 provider는 False."""
    key_attr = _PROVIDER_KEY_ATTRS.get(provider)
    if key_attr is None:
        return False
    return bool(getattr(settings, key_attr, None))


def _default_chat_model(provider: str) -> str | None:
    if provider == "google":
        return DEFAULT_GEMINI_MODEL
    if provider == "anthropic":
        return DEFAULT_ANTHROPIC_MODEL
    if provider == "openai":
        return DEFAULT_OPENAI_CHAT_MODEL
    return None


def _google_chat_model_candidates(selected_model: str) -> list[str]:
    """기존 동작 + upstream 테스트(test_llm_client.py)가 import하므로 그대로 보존."""
    if selected_model == DEFAULT_GEMINI_FALLBACK_MODEL:
        return [selected_model]
    return [selected_model, DEFAULT_GEMINI_FALLBACK_MODEL]


def _is_google_high_demand_error(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    text = str(error).lower()
    return status_code == 503 or "503" in text or "high demand" in text or "unavailable" in text


def _should_retry_with_gemini_fallback(
    provider: str,
    model: str | None,
    error: Exception,
) -> bool:
    return (
        provider == "google"
        and model != DEFAULT_GEMINI_FALLBACK_MODEL
        and _is_google_high_demand_error(error)
    )


llm = LLMGateway()
