"""입출력 가드레일 — BR-05 종목 매수/매도 추천 차단."""

import re

from pydantic import BaseModel

# BR-05: 멘토는 어떤 경우에도 매수/매도를 직접 추천하지 않는다.
_FORBIDDEN_OUTPUT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:매수|매도)\s*(?:를)?\s*(?:추천|권유|권장)", re.IGNORECASE),
    re.compile(r"(?:사세요|파세요|살\s*것|팔\s*것|지금\s*(?:사|팔))", re.IGNORECASE),
    re.compile(r"\b(buy|sell)\s+(?:recommendation|now|this)\b", re.IGNORECASE),
    re.compile(r"target\s+price\s*[:=]?\s*\d", re.IGNORECASE),
]


class GuardrailResult(BaseModel):
    ok: bool
    reason: str | None = None


class PromptGuardrail:
    def check_input(self, text: str) -> GuardrailResult:
        # 사용자 입력은 통과 — 사용자가 "매수 추천해줘"라고 물어볼 권리는 있다.
        # 멘토의 답변 단계에서 차단(check_output)으로 BR-05 만족.
        return GuardrailResult(ok=True)

    def check_output(self, text: str) -> GuardrailResult:
        for pattern in _FORBIDDEN_OUTPUT_PATTERNS:
            if pattern.search(text):
                return GuardrailResult(
                    ok=False,
                    reason="종목 매수·매도 추천은 제공하지 않습니다 (금융소비자보호법 / BR-05).",
                )
        return GuardrailResult(ok=True)


guardrail = PromptGuardrail()

__all__ = ["GuardrailResult", "PromptGuardrail", "guardrail"]
