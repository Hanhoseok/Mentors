"""LLM 공통 DTO.

client.py / gateway.py / 호출 측이 공유하는 Pydantic 모델. provider별 응답을
이 형태로 정규화해서 caller는 OpenAI/Anthropic/Gemini를 신경 쓰지 않는다.

⚠️  BaseModel을 그대로 사용하는 이유:
    learning/service.py 등에서 `chunk.model_dump_json()`을 사용하므로 Pydantic API
    유지 필수. dataclass로 바꾸면 SSE 스트리밍이 깨진다.
"""

from typing import Any

from pydantic import BaseModel, Field

from core.contracts import MessageRole


class Message(BaseModel):
    role: MessageRole
    content: str


class ChatResponse(BaseModel):
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class StreamChunk(BaseModel):
    delta: str
    done: bool
    usage: dict[str, Any] | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)


__all__ = ["ChatResponse", "Message", "StreamChunk"]
