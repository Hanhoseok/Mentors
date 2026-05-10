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
