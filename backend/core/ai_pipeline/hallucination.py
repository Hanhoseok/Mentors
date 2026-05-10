"""환각 검출 — RAG 컨텍스트 외 응답 차단 (NFR-04, BR-02, QAS-02)."""

from .rag import RAGContext


class HallucinationDetector:
    """MVP 휴리스틱:
    - 컨텍스트가 비어있고 답변이 길면 환각으로 간주
    - 향후 LLM-as-judge로 강화 (v2)
    """

    EMPTY_CONTEXT_MAX_CHARS: int = 200

    async def verify(self, answer: str, context: RAGContext) -> bool:
        if context.is_empty:
            # 컨텍스트가 없는데 답변이 길면 일반 지식 답변(환각 위험)
            return len(answer) <= self.EMPTY_CONTEXT_MAX_CHARS
        # 컨텍스트가 있으면 통과 (LLM-as-judge는 v2)
        return True


hallucination = HallucinationDetector()

__all__ = ["HallucinationDetector", "hallucination"]
