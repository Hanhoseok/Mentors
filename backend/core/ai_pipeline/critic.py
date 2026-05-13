"""페르소나 일치도·답변 다양성 검증 (NFR-06, NFR-08)."""

from pydantic import BaseModel

from .rag import RAGContext


class CriticResult(BaseModel):
    ok: bool
    persona_score: float  # NFR-06: 0.7+ 권장
    distinct_n: float  # NFR-08: 0.7+ 권장
    reason: str | None = None


class CriticFilter:
    """MVP 더미 — 향후 별도 LLM judge로 페르소나 일치도 평가 (v2).

    - persona_score: 멘토 철학 일치도 (현재 휴리스틱 0.85 고정)
    - distinct_n: bigram diversity ratio
    """

    PERSONA_THRESHOLD: float = 0.7
    DISTINCT_N_THRESHOLD: float = 0.7

    async def evaluate(
        self,
        answer: str,
        persona_id: str,
        context: RAGContext,
    ) -> CriticResult:
        persona_score = await self._score_persona(answer, persona_id, context)
        distinct_n = self._distinct_n(answer, n=2)

        if persona_score < self.PERSONA_THRESHOLD:
            return CriticResult(
                ok=False,
                persona_score=persona_score,
                distinct_n=distinct_n,
                reason=f"페르소나 일치도 미달 ({persona_score:.2f} < {self.PERSONA_THRESHOLD})",
            )
        if distinct_n < self.DISTINCT_N_THRESHOLD:
            return CriticResult(
                ok=False,
                persona_score=persona_score,
                distinct_n=distinct_n,
                reason=f"답변 다양성 미달 ({distinct_n:.2f} < {self.DISTINCT_N_THRESHOLD})",
            )
        return CriticResult(ok=True, persona_score=persona_score, distinct_n=distinct_n)

    async def _score_persona(
        self,
        answer: str,
        persona_id: str,
        context: RAGContext,
    ) -> float:
        # MVP 더미. v2: 별도 LLM judge로 평가.
        return 0.85

    @staticmethod
    def _distinct_n(text: str, n: int = 2) -> float:
        tokens = text.split()
        if len(tokens) < n:
            return 1.0
        ngrams = [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
        if not ngrams:
            return 1.0
        return len(set(ngrams)) / len(ngrams)


critic = CriticFilter()

__all__ = ["CriticFilter", "CriticResult", "critic"]
