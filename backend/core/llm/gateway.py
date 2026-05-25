"""LLM 호출 정책 레이어.

client.py는 provider별 실제 API 호출만 담당하고, 이 모듈은 provider/model 선택,
fallback, response_format 같은 공통 호출 정책을 담당한다.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from core.config import settings
from core.exceptions import ExternalServiceError

from .client import DEFAULT_GEMINI_MODEL, LLMClient, llm_client
from .dto import ChatResponse, Message, StreamChunk

logger = logging.getLogger("llm")

DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash-lite"


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
    ) -> ChatResponse:
        selected_provider = provider or settings.llm_provider
        selected_model = model or _default_chat_model(selected_provider)
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
    ) -> AsyncIterator[StreamChunk]:
        selected_provider = provider or settings.llm_provider
        selected_model = model or _default_chat_model(selected_provider)
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

    async def embed(self, text: str) -> list[float]:
        return await self._client.embed(text)


def _default_chat_model(provider: str) -> str | None:
    if provider == "google":
        return DEFAULT_GEMINI_MODEL
    return None


def _google_chat_model_candidates(selected_model: str) -> list[str]:
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
