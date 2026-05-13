"""출처 추적 — NFR-05 (주요 주장 60~70% 출처 명시)."""

import re

from pydantic import BaseModel

from .rag import RAGContext

_CITATION_PATTERN = re.compile(r"\[(?:출처|source)\s*:\s*([^\]]+)\]", re.IGNORECASE)


class Citation(BaseModel):
    text: str
    source_id: str


class CitationTracker:
    """LLM이 답변에 `[출처: doc_id]` 형식을 삽입하면 추출.

    프롬프트에서 LLM에게 이 포맷을 지시해야 한다 (학습 동의 책임).
    """

    def extract(self, answer: str, context: RAGContext) -> list[Citation]:
        valid_ids = {d.id for d in context.documents}
        citations: list[Citation] = []
        for match in _CITATION_PATTERN.finditer(answer):
            raw = match.group(1).strip()
            if raw in valid_ids:
                citations.append(Citation(text=match.group(0), source_id=raw))
        return citations


citation = CitationTracker()

__all__ = ["Citation", "CitationTracker", "citation"]
