"""일일 리포트 생성용 프롬프트.

daily_report 동이 리포트의 '목소리'를 직접 소유한다. 학습 동의 페르소나
프롬프트(features/learning/personas)를 가져오면 동 경계(ADR-014)를 침범하므로,
전략별 해석 렌즈를 여기서 가볍게 따로 정의한다.
"""

from core.ai_pipeline import tier_overlay
from core.contracts import MentorStrategy, MessageRole, Tier
from core.llm import Message
from core.read_services import ConceptRef, NewsRef

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

# 리포트 도입 + 공통 섹션(1~3). 섹션 4·5는 학습 개념 고정 여부에 따라 달라진다.
_REPORT_INTRO = (
    "독자는 투자를 막 시작한 초보자다. 리포트를 다 읽고 나면 '이해됐다 / 오늘 뭘 "
    "공부하면 될지 알겠다 / 멘토에게 이걸 물어봐야겠다'는 생각이 들어야 한다.\n\n"
    "출력 형식 (마크다운):\n"
    "1. 독자 닉네임을 부르는 따뜻한 한 문장 인사 + 오늘 가장 중요한 한 가지를 "
    "쉬운 말로 요약한 핵심 메시지 한 줄\n"
    "2. '## 오늘의 시장' — 제공된 뉴스에 실제로 등장한 사건·기업을 근거로 2~3문장. "
    "초보자가 이해하도록 쉬운 말로, '그래서 이게 왜 의미 있는지'까지 풀어 설명한다. "
    "뉴스에 없는 일반론·추측은 쓰지 않는다.\n"
    "3. '## 주목할 소식' — 제공된 뉴스 중 이 전략 관점에서 가장 의미 있는 1~2개를 "
    "'- ' 불릿으로. 각 항목은 '무슨 일인지' 한 문장 + '그래서 이런 투자자에게 왜 "
    "중요한지' 한 문장으로 쓴다.\n"
)

_REPORT_RULES = (
    "규칙: 뉴스가 제공되면 반드시 그 내용을 근거로 쓴다('특별한 뉴스가 없다'는 식의 "
    "회피 금지). 투자 권유·단정적 수익 보장·매수매도 지시는 금지. 전문용어는 처음 "
    "나올 때 괄호로 짧게 풀어 쓴다. 정보 제공과 학습 동기 자극에 집중한다. "
    "전체 500~800자 내외."
)

# 학습 개념을 못 고른 경우(티어·커리큘럼 없음 등)의 자유 선택 폴백 섹션 4·5.
_FREEFORM_CONCEPT_SECTIONS = (
    "4. '## 오늘 알아두면 좋은 개념' — 위 뉴스를 이해하는 데 핵심이 되는 투자 개념을 "
    "딱 1개만 골라, 개념 이름을 **굵게** 표시하고 초보자도 이해할 단어로 2문장 정의한 뒤, "
    "'이 개념을 알면 ~를 스스로 해석할 수 있어요'처럼 공부할 동기를 한 문장 준다. "
    "오늘 뉴스 맥락과 직접 연결된 개념이어야 한다.\n"
    "5. '## 멘토에게 이렇게 물어보세요' — 독자가 그대로 복사해 멘토에게 보낼 수 있는 "
    "구체적인 질문 2개를 '- ' 불릿으로. 막연한 질문이 아니라 오늘의 뉴스·개념과 직접 "
    "이어진, 물음표로 끝나는 완성된 질문 문장이어야 한다.\n"
)


def _curriculum_concept_sections(concept: ConceptRef) -> str:
    """학습 동이 고른 진도순 개념으로 섹션 4·5를 고정한다.

    섹션 5의 질문에 개념 trigger 키워드를 반드시 포함시키는 게 핵심이다. 사용자가
    그 질문을 멘토에게 보내면 concept_detector가 같은 개념을 인식해 팔로우업 퀴즈를
    띄우므로, 리포트→대화→퀴즈가 커리큘럼 안에서 닫힌 루프가 된다.
    """
    keywords = ", ".join(f"'{kw}'" for kw in concept.keywords[:6]) or f"'{concept.title}'"
    return (
        "4. '## 오늘 알아두면 좋은 개념' — 오늘의 학습 개념은 반드시 "
        f"**{concept.title}**(으)로 한다. 임의의 다른 개념으로 바꾸지 않는다. "
        f"개념 이름 **{concept.title}**을(를) 굵게 표시하고, 초보자도 이해할 쉬운 "
        "말로 2문장 정의한 뒤, 오늘 뉴스 사례와 연결해 '이 개념을 알면 ~를 스스로 "
        "해석할 수 있어요'처럼 공부할 동기를 한 문장 준다.\n"
        "5. '## 멘토에게 이렇게 물어보세요' — 위 학습 개념"
        f"({concept.title})을(를) 멘토와 더 깊이 파고드는 질문 2개를 '- ' 불릿으로. "
        f"두 질문 모두 다음 표현 중 최소 1개를 자연스럽게 포함해야 한다: {keywords}. "
        "막연한 일반론이 아니라 이 개념을 중심으로 오늘 뉴스와 이어진, 물음표로 "
        "끝나는 완성된 질문이어야 한다.\n"
    )


def _report_format(concept: ConceptRef | None) -> str:
    sections = (
        _curriculum_concept_sections(concept)
        if concept is not None
        else _FREEFORM_CONCEPT_SECTIONS
    )
    return f"{_REPORT_INTRO}{sections}{_REPORT_RULES}"


def _news_block(news: list[NewsRef]) -> str:
    if not news:
        return "(오늘 선별된 뉴스 없음)"
    return "\n".join(f"- [{int(n.id)}] {n.title}" for n in news)


def build_market_summary_prompt(news: list[NewsRef]) -> list[Message]:
    """멘토 무관 중립 시장 요약 (공통 코어용)."""
    system = (
        "너는 중립적인 시장 애널리스트다. 특정 투자 전략에 치우치지 않고, 아래 제공된 "
        "뉴스에 실제로 등장한 사건·기업·지표를 근거로 오늘의 흐름을 2~3문장으로 "
        "구체적으로 요약한다. 뉴스에 없는 추측이나 투자 권유는 하지 않는다."
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
    concept: ConceptRef | None = None,
) -> list[Message]:
    """멘토 전략 렌즈 + 티어 깊이로 개인화된 일일 브리핑.

    concept이 주어지면 '오늘 알아두면 좋은 개념'을 그 커리큘럼 개념으로 고정하고,
    멘토 질문에 개념 trigger 키워드를 심어 채팅 팔로우업 퀴즈가 발생하도록 한다.
    """
    lens = _STRATEGY_LENS.get(strategy, _STRATEGY_LENS[MentorStrategy.VALUE])
    system = tier_overlay.apply(f"{lens}\n\n{_report_format(concept)}", tier)
    concept_line = (
        f"\n[오늘의 학습 개념]\n{concept.title} (이 개념을 섹션 4·5의 중심으로 삼는다)\n"
        if concept is not None
        else ""
    )
    user = (
        f"독자: {nickname}님 (티어 {tier.value})\n\n"
        f"[중립 시장 요약]\n{market_summary or '(요약 없음)'}\n"
        f"{concept_line}\n"
        f"[오늘의 뉴스]\n{_news_block(news)}\n\n"
        f"{nickname}님을 위한 오늘의 리포트를 작성해줘."
    )
    return [
        Message(role=MessageRole.SYSTEM, content=system),
        Message(role=MessageRole.USER, content=user),
    ]


__all__ = ["build_market_summary_prompt", "build_report_prompt"]
