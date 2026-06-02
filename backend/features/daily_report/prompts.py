"""일일 리포트 생성용 프롬프트.

daily_report 동이 리포트의 '목소리'를 직접 소유한다. 학습 동의 페르소나
프롬프트(features/learning/personas)를 가져오면 동 경계(ADR-014)를 침범하므로,
전략별 해석 렌즈를 여기서 가볍게 따로 정의한다.
"""

from core.ai_pipeline import tier_overlay
from core.contracts import MentorStrategy, MessageRole, Tier
from core.llm import Message
from core.read_services import NewsRef

# 전략별 해석 렌즈 — 같은 뉴스를 어떤 관점으로 읽을지.
_STRATEGY_LENS: dict[MentorStrategy, str] = {
    MentorStrategy.VALUE: (
        "너는 가치투자 멘토다. 내재가치 대비 가격, 안전마진, 기업 펀더멘털 관점에서 "
        "오늘의 시장을 해석한다. 단기 급등락보다 장기 본질 가치에 주목한다."
    ),
    MentorStrategy.GROWTH: (
        "너는 성장투자 멘토다. 매출·이익 성장성, 시장 확장, 미래 잠재력 관점에서 "
        "오늘의 시장을 해석한다. 성장 모멘텀과 산업 트렌드에 주목한다."
    ),
    MentorStrategy.DIVIDEND: (
        "너는 배당투자 멘토다. 배당 안정성, 현금흐름, 주주환원 관점에서 오늘의 "
        "시장을 해석한다. 변동성보다 꾸준한 인컴과 재무 건전성에 주목한다."
    ),
    MentorStrategy.MOMENTUM: (
        "너는 모멘텀투자 멘토다. 가격·거래량 추세와 시장 심리 관점에서 오늘의 "
        "시장을 해석한다. 현재 흐름의 강도와 전환 신호에 주목한다."
    ),
}

_REPORT_FORMAT = (
    "출력 형식 (마크다운):\n"
    "1. 한 문장 인사 + 오늘의 핵심 메시지\n"
    "2. '## 오늘의 시장' — 2~3문장으로 시장 흐름을 네 전략 렌즈로 해석\n"
    "3. '## 주목할 소식' — 아래 뉴스 중 1~2개를 골라 왜 중요한지 렌즈로 설명\n"
    "4. '## 오늘의 한 걸음' — 사용자가 멘토와 대화를 시작하고 싶게 만드는 질문 한 줄\n"
    "투자 권유나 단정적 수익 보장은 금지. 정보 제공과 사고 자극에 집중한다."
)


def _news_block(news: list[NewsRef]) -> str:
    if not news:
        return "(오늘 선별된 뉴스 없음)"
    return "\n".join(f"- [{int(n.id)}] {n.title}" for n in news)


def build_market_summary_prompt(news: list[NewsRef]) -> list[Message]:
    """멘토 무관 중립 시장 요약 (공통 코어용)."""
    system = (
        "너는 중립적인 시장 애널리스트다. 특정 투자 전략에 치우치지 않고 "
        "오늘의 뉴스 흐름을 2~3문장으로 객관적으로 요약한다. 투자 권유는 하지 않는다."
    )
    user = f"오늘의 주요 뉴스:\n{_news_block(news)}\n\n위 흐름을 중립적으로 요약해줘."
    return [
        Message(role=MessageRole.SYSTEM, content=system),
        Message(role=MessageRole.USER, content=user),
    ]


def build_report_prompt(
    strategy: MentorStrategy,
    tier: Tier,
    nickname: str,
    news: list[NewsRef],
    market_summary: str | None,
) -> list[Message]:
    """멘토 전략 렌즈 + 티어 깊이로 개인화된 일일 브리핑."""
    lens = _STRATEGY_LENS.get(strategy, _STRATEGY_LENS[MentorStrategy.VALUE])
    system = tier_overlay.apply(f"{lens}\n\n{_REPORT_FORMAT}", tier)
    user = (
        f"독자: {nickname}님 (티어 {tier.value})\n\n"
        f"[중립 시장 요약]\n{market_summary or '(요약 없음)'}\n\n"
        f"[오늘의 뉴스]\n{_news_block(news)}\n\n"
        f"{nickname}님을 위한 오늘의 리포트를 작성해줘."
    )
    return [
        Message(role=MessageRole.SYSTEM, content=system),
        Message(role=MessageRole.USER, content=user),
    ]


__all__ = ["build_market_summary_prompt", "build_report_prompt"]
