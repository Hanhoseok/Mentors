"""LLM provider 추상화 (§4.7, ADR-010, ADR-012).

OpenAI / Anthropic / Google Gemini 셋 다 지원. chat()/chat_stream()/embed() 모두
settings.llm_provider에 따라 분기 (Anthropic은 native 임베딩이 없으므로 embed는
google/openai 선택 필요).
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
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GEMINI_EMBED_MODEL = "gemini-embedding-001"


class LLMClient:
    def __init__(self) -> None:
        self._openai: AsyncOpenAI | None = None
        self._anthropic: AsyncAnthropic | None = None
        self._google: Any | None = None

        if settings.openai_api_key:
            from openai import AsyncOpenAI

            self._openai = AsyncOpenAI(api_key=settings.openai_api_key)

        if settings.anthropic_api_key:
            from anthropic import AsyncAnthropic

            self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)

        if settings.gemini_api_key:
            from google import genai

            self._google = genai.Client(api_key=settings.gemini_api_key)

    @property
    def configured(self) -> bool:
        return self._openai is not None or self._anthropic is not None or self._google is not None

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
        if selected_provider == "openai" and self._openai is not None:
            return await self._openai_chat(messages, model, temperature, max_tokens)
        if selected_provider == "anthropic" and self._anthropic is not None:
            return await self._anthropic_chat(messages, model, temperature, max_tokens)
        if selected_provider == "google" and self._google is not None:
            return await self._google_chat(
                messages,
                model,
                temperature,
                max_tokens,
                response_format,
            )
        raise ExternalServiceError(f"{selected_provider} chat not configured (missing API key)")

    async def chat_stream(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        provider: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        selected_provider = provider or settings.llm_provider
        if selected_provider == "openai" and self._openai is not None:
            async for chunk in self._openai_chat_stream(messages, model, temperature, max_tokens):
                yield chunk
            return
        if selected_provider == "anthropic" and self._anthropic is not None:
            async for chunk in self._anthropic_chat_stream(
                messages, model, temperature, max_tokens
            ):
                yield chunk
            return
        if selected_provider == "google" and self._google is not None:
            async for chunk in self._google_chat_stream(messages, model, temperature, max_tokens):
                yield chunk
            return
        raise ExternalServiceError(
            f"{selected_provider} chat_stream not configured (missing API key)"
        )

    async def embed(self, text: str) -> list[float]:
        if settings.llm_provider == "openai" and self._openai is not None:
            try:
                resp = await self._openai.embeddings.create(
                    model=DEFAULT_OPENAI_EMBED_MODEL,
                    input=text,
                )
            except Exception as e:
                raise ExternalServiceError(f"OpenAI embed failed: {e}") from e
            return list(resp.data[0].embedding)

        if settings.llm_provider == "google" and self._google is not None:
            return await self._google_embed(text)

        if settings.llm_provider == "anthropic":
            raise ExternalServiceError(
                "embed() not available for Anthropic (no native embeddings); "
                "set LLM_PROVIDER=google or openai"
            )

        raise ExternalServiceError(
            f"{settings.llm_provider} embed not configured (missing API key)"
        )

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

    # --- Google Gemini ---

    @staticmethod
    def _to_google_contents(
        messages: list[Message],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts = [m.content for m in messages if m.role == MessageRole.SYSTEM]
        system = "\n\n".join(system_parts) if system_parts else None

        contents = []
        for m in messages:
            if m.role == MessageRole.SYSTEM:
                continue
            role = "model" if m.role == MessageRole.ASSISTANT else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        return (system, contents)

    async def _google_chat(
        self,
        messages: list[Message],
        model: str | None,
        temperature: float,
        max_tokens: int,
        response_format: str | None,
    ) -> ChatResponse:
        assert self._google is not None
        from google.genai import types

        system, contents = self._to_google_contents(messages)
        config = types.GenerateContentConfig(
            temperature=temperature,
            maxOutputTokens=max_tokens,
            thinkingConfig=types.ThinkingConfig(thinkingBudget=0),
        )
        if response_format == "json":
            config.response_mime_type = "application/json"
        if system is not None:
            config.system_instruction = system

        selected_model = model or DEFAULT_GEMINI_MODEL
        try:
            resp = await self._google.aio.models.generate_content(
                model=selected_model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            raise ExternalServiceError(f"Google Gemini chat failed: {e}") from e

        usage = getattr(resp, "usage_metadata", None)
        return ChatResponse(
            text=resp.text or "",
            model=getattr(resp, "model_version", None) or selected_model,
            prompt_tokens=usage.prompt_token_count if usage else 0,
            completion_tokens=usage.candidates_token_count if usage else 0,
        )

    async def _google_chat_stream(
        self,
        messages: list[Message],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[StreamChunk]:
        assert self._google is not None
        from google.genai import types

        system, contents = self._to_google_contents(messages)
        config = types.GenerateContentConfig(
            temperature=temperature,
            maxOutputTokens=max_tokens,
            thinkingConfig=types.ThinkingConfig(thinkingBudget=0),
        )
        if system is not None:
            config.system_instruction = system

        selected_model = model or DEFAULT_GEMINI_MODEL
        try:
            stream = await self._google.aio.models.generate_content_stream(
                model=selected_model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            raise ExternalServiceError(f"Google Gemini stream init failed: {e}") from e

        usage_dict: dict[str, Any] | None = None
        async for chunk in stream:
            if chunk.text:
                yield StreamChunk(delta=chunk.text, done=False)
            usage = getattr(chunk, "usage_metadata", None)
            if usage is not None:
                usage_dict = {
                    "prompt_tokens": usage.prompt_token_count,
                    "completion_tokens": usage.candidates_token_count,
                }

        yield StreamChunk(delta="", done=True, usage=usage_dict)

    async def _google_embed(self, text: str) -> list[float]:
        assert self._google is not None
        try:
            resp = await self._google.aio.models.embed_content(
                model=DEFAULT_GEMINI_EMBED_MODEL,
                contents=[text],
            )
        except Exception as e:
            raise ExternalServiceError(f"Google Gemini embed failed: {e}") from e
        if not resp.embeddings or not resp.embeddings[0].values:
            raise ExternalServiceError("Google Gemini embed returned no embedding")
        return list(resp.embeddings[0].values)


llm_client = LLMClient()
