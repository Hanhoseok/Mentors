"""core.llm 패키지.

호출 측은 항상 gateway의 싱글톤 `llm`을 사용한다. provider별 raw 호출이 필요하면
`llm_client`를 import해도 되지만 일반적으로는 정책 레이어를 거치는 게 안전하다.
"""

from .client import LLMClient, llm_client
from .dto import ChatResponse, Message, StreamChunk
from .gateway import LLMGateway, llm

__all__ = [
    "ChatResponse",
    "LLMClient",
    "LLMGateway",
    "Message",
    "StreamChunk",
    "llm",
    "llm_client",
]
