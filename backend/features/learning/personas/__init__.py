"""멘토 전략 매핑 및 페르소나 관리."""

from core.contracts import MentorStrategy

from .dividend import SYSTEM_PROMPT as DIVIDEND_PROMPT
from .growth import SYSTEM_PROMPT as GROWTH_PROMPT
from .momentum import SYSTEM_PROMPT as MOMENTUM_PROMPT
from .value import SYSTEM_PROMPT as VALUE_PROMPT


def get_mentor_strategy(mentor_id: int) -> MentorStrategy:
    """멘토 ID를 기반으로 내재된 투자 전략을 반환한다."""
    mapping = {
        1: MentorStrategy.VALUE,
        2: MentorStrategy.GROWTH,
        3: MentorStrategy.DIVIDEND,
        4: MentorStrategy.MOMENTUM,
    }
    return mapping.get(mentor_id, MentorStrategy.VALUE)


def get_system_prompt(strategy: MentorStrategy) -> str:
    """투자 전략에 따른 시스템 프롬프트를 반환한다."""
    prompts = {
        MentorStrategy.VALUE: VALUE_PROMPT,
        MentorStrategy.GROWTH: GROWTH_PROMPT,
        MentorStrategy.DIVIDEND: DIVIDEND_PROMPT,
        MentorStrategy.MOMENTUM: MOMENTUM_PROMPT,
    }
    return prompts.get(strategy, VALUE_PROMPT)


# 그날 그 멘토 첫 진입 시 일일 리포트 카드 위에 얹는 짧은 멘토 인사.
_OPENERS: dict[MentorStrategy, str] = {
    MentorStrategy.VALUE: "가치투자 멘토예요. 오늘 시장, 본질 가치 관점에서 같이 짚어볼까요?",
    MentorStrategy.GROWTH: "성장투자 멘토예요. 오늘은 어떤 성장 신호가 보이는지 같이 살펴봐요.",
    MentorStrategy.DIVIDEND: "배당투자 멘토예요. 오늘 시장 흐름, 꾸준함의 관점에서 함께 봐요.",
    MentorStrategy.MOMENTUM: "모멘텀투자 멘토예요. 오늘 흐름의 방향, 같이 읽어볼까요?",
}


def get_opener(strategy: MentorStrategy) -> str:
    """전략별 멘토 인사 오프너 (일일 리포트 카드 헤더용)."""
    return _OPENERS.get(strategy, _OPENERS[MentorStrategy.VALUE])


__all__ = ["get_mentor_strategy", "get_opener", "get_system_prompt"]
