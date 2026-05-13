"""LLM provider 추상화 (§4.7, ADR-010, ADR-012).

OpenAI / Anthropic 둘 다 지원. embed()는 OpenAI 전용 (Anthropic은 native 임베딩 없음).
chat()/chat_stream()은 settings.llm_provider에 따라 분기.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

from core.config import settings
from core.contracts import MessageRole
from core.exceptions import ExternalServiceError

from .dto import ChatResponse, Message, StreamChunk

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic
    from openai import AsyncOpenAI

logger = logging.getLogger("llm")

DEFAULT_OPENAI_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


class LLMClient:
    def __init__(self) -> None:
        self._openai: AsyncOpenAI | None = None
        self._anthropic: AsyncAnthropic | None = None

        if settings.openai_api_key:
            from openai import AsyncOpenAI

            self._openai = AsyncOpenAI(api_key=settings.openai_api_key)

        if settings.anthropic_api_key:
            from anthropic import AsyncAnthropic

            self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

    @property
    def configured(self) -> bool:
        return self._openai is not None or self._anthropic is not None

    async def chat(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> ChatResponse:
        if settings.llm_provider == "openai" and self._openai is not None:
            return await self._openai_chat(messages, model, temperature, max_tokens)
        if settings.llm_provider == "anthropic" and self._anthropic is not None:
            return await self._anthropic_chat(messages, model, temperature, max_tokens)
        raise ExternalServiceError(f"{settings.llm_provider} chat not configured (missing API key)")

    async def chat_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> AsyncIterator[StreamChunk]:
        if settings.llm_provider == "openai" and self._openai is not None:
            async for chunk in self._openai_chat_stream(messages, model, temperature, max_tokens):
                yield chunk
            return
        if settings.llm_provider == "anthropic" and self._anthropic is not None:
            async for chunk in self._anthropic_chat_stream(
                messages, model, temperature, max_tokens
            ):
                yield chunk
            return
        raise ExternalServiceError(
            f"{settings.llm_provider} chat_stream not configured (missing API key)"
        )

    async def embed(self, text: str) -> list[float]:
        if self._openai is None:
            raise ExternalServiceError(
                "embed() requires OPENAI_API_KEY (Anthropic has no native embeddings)"
            )
        try:
            resp = await self._openai.embeddings.create(
                model=DEFAULT_OPENAI_EMBED_MODEL,
                input=text,
            )
        except Exception as e:
            raise ExternalServiceError(f"OpenAI embed failed: {e}") from e
        return list(resp.data[0].embedding)

    # --- OpenAI ---

    @staticmethod
    def _to_openai_messages(messages: list[Message]) -> Any:
        return cast(Any, [{"role": m.role.value, "content": m.content} for m in messages])

    async def _openai_chat(
        self,
        messages: list[Message],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> ChatResponse:
        assert self._openai is not None
        try:
            resp = await self._openai.chat.completions.create(
                model=model or DEFAULT_OPENAI_CHAT_MODEL,
                messages=self._to_openai_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=settings.llm_stream_timeout_s,
            )
        except Exception as e:
            raise ExternalServiceError(f"OpenAI chat failed: {e}") from e

        choice = resp.choices[0]
        usage = resp.usage
        return ChatResponse(
            text=choice.message.content or "",
            model=resp.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    async def _openai_chat_stream(
        self,
        messages: list[Message],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[StreamChunk]:
        assert self._openai is not None
        try:
            stream = await self._openai.chat.completions.create(
                model=model or DEFAULT_OPENAI_CHAT_MODEL,
                messages=self._to_openai_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
                timeout=settings.llm_stream_timeout_s,
            )
        except Exception as e:
            raise ExternalServiceError(f"OpenAI stream init failed: {e}") from e

        usage: dict[str, Any] | None = None
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield StreamChunk(delta=chunk.choices[0].delta.content, done=False)
            if chunk.usage is not None:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                }
        yield StreamChunk(delta="", done=True, usage=usage)

    # --- Anthropic ---

    @staticmethod
    def _split_system(messages: list[Message]) -> tuple[str | None, list[dict[str, str]]]:
        system_parts = [m.content for m in messages if m.role == MessageRole.SYSTEM]
        non_system = [
            {"role": m.role.value, "content": m.content}
            for m in messages
            if m.role != MessageRole.SYSTEM
        ]
        return ("\n\n".join(system_parts) if system_parts else None, non_system)

    async def _anthropic_chat(
        self,
        messages: list[Message],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> ChatResponse:
        assert self._anthropic is not None
        system, non_system = self._split_system(messages)
        kwargs: dict[str, Any] = {
            "model": model or DEFAULT_ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": non_system,
        }
        if system is not None:
            kwargs["system"] = system
        try:
            resp = await self._anthropic.messages.create(**kwargs)
        except Exception as e:
            raise ExternalServiceError(f"Anthropic chat failed: {e}") from e

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        return ChatResponse(
            text=text,
            model=resp.model,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
        )

    async def _anthropic_chat_stream(
        self,
        messages: list[Message],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[StreamChunk]:
        assert self._anthropic is not None
        system, non_system = self._split_system(messages)
        kwargs: dict[str, Any] = {
            "model": model or DEFAULT_ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": non_system,
        }
        if system is not None:
            kwargs["system"] = system

        try:
            async with self._anthropic.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(delta=text, done=False)
                final = await stream.get_final_message()
        except Exception as e:
            raise ExternalServiceError(f"Anthropic stream failed: {e}") from e

        yield StreamChunk(
            delta="",
            done=True,
            usage={
                "prompt_tokens": final.usage.input_tokens,
                "completion_tokens": final.usage.output_tokens,
            },
        )


llm = LLMClient()
