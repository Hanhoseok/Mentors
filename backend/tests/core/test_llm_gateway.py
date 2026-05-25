import pytest

from core.contracts import MessageRole
from core.exceptions import ExternalServiceError
from core.llm.dto import ChatResponse, Message
from core.llm.gateway import DEFAULT_GEMINI_FALLBACK_MODEL, LLMGateway


class FakeLLMClient:
    configured = True

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def chat(
        self,
        messages,
        model=None,
        temperature=0.7,
        max_tokens=1000,
        response_format=None,
        provider=None,
    ):
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
                "provider": provider,
            }
        )
        if len(self.calls) == 1:
            raise ExternalServiceError("Google Gemini chat failed: 503 UNAVAILABLE high demand")
        return ChatResponse(text="{}", model=str(model), prompt_tokens=1, completion_tokens=1)

    async def embed(self, text: str) -> list[float]:
        return [float(len(text))]


@pytest.mark.asyncio
async def test_gateway_retries_google_high_demand_with_flash_lite(monkeypatch) -> None:
    monkeypatch.setattr("core.llm.gateway.settings.llm_provider", "google")
    client = FakeLLMClient()
    gateway = LLMGateway(client=client)  # type: ignore[arg-type]

    response = await gateway.chat(
        [Message(role=MessageRole.USER, content="반드시 JSON만 출력하세요.")],
        response_format="json",
    )

    assert response.model == DEFAULT_GEMINI_FALLBACK_MODEL
    assert len(client.calls) == 2
    assert client.calls[0]["provider"] == "google"
    assert client.calls[0]["response_format"] == "json"
    assert client.calls[1]["model"] == DEFAULT_GEMINI_FALLBACK_MODEL
