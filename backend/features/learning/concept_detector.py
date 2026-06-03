from __future__ import annotations

from core.contracts import Tier
from features.growth.catalog import list_concepts_for_tier

from .tier_quizzes import TierQuiz, list_tier_quizzes

_CONCEPT_KEYWORDS: dict[int, tuple[str, ...]] = {
    # T1 기초
    101: ("안전마진", "안전 마진", "싸게 사기", "할인 매수"),
    102: ("내재가치", "적정가치", "본질가치", "본질 가치"),
    103: ("장기투자", "장기 투자", "오래 보유"),
    104: ("변동성", "위험", "주가 하락", "가격 흔들림"),
    105: ("좋은 기업", "좋은 사업", "현금흐름 사업"),
    106: ("복리", "복리 효과", "이자에 이자", "복리 투자"),
    107: ("분산투자", "분산", "여러 종목", "달걀 바구니"),
    108: ("per", "주가수익비율", "이익 대비 주가", "수익배수"),
    109: ("배당", "배당금", "주주 환원", "배당주"),
    110: ("타이밍", "바닥", "천장", "언제 살지", "매수 타이밍"),
    # T2 초급
    201: ("트레이드오프", "트레이드 오프", "장단점 비교", "기회비용"),
    202: ("반대 의견", "반대 논리", "반론", "다른 관점"),
    203: ("비중", "포지션 사이즈", "한 종목 비중", "몰빵"),
    204: ("포트폴리오", "상관관계", "섹터 쏠림"),
    205: ("투자 논리", "매수 이유", "매도 기준", "가설 점검"),
    206: ("재무제표", "손익계산서", "영업이익", "당기순이익"),
    207: ("pbr", "주가순자산비율", "장부가치", "순자산"),
    208: ("영업이익률", "마진", "원가율", "비용 효율"),
    209: ("부채비율", "부채", "레버리지", "이자 부담"),
    210: ("roe", "자기자본이익률", "자본 수익률", "주주 수익률"),
    # T3 중급
    301: ("다양한 관점", "여러 멘토", "서로 다른 관점", "관점 비교"),
    302: ("섹터", "섹터 순환", "업종 순환", "업종 이동"),
    303: ("매크로", "pmi", "cpi", "실업률"),
    304: ("시나리오", "기본 시나리오", "낙관 시나리오", "비관 시나리오"),
    305: ("리밸런싱", "자산 배분", "현금 비중"),
    306: ("금리 주식", "금리와 주가", "금리 영향", "할인율"),
    307: ("환율", "원달러", "외환", "달러 강세"),
    308: ("eps", "주당순이익", "이익 성장", "earnings"),
    309: ("성장주", "가치주", "growth stock", "value stock"),
    310: ("gdp", "경제 성장률", "경기 지표", "경기 흐름"),
    # T4 중상급
    401: ("금리", "금리 인상", "금리 인하", "금리 민감도"),
    402: ("매크로 국면", "경기 국면", "인플레이션", "경기 둔화"),
    403: ("이익의 질", "재고 증가", "일회성 이익", "현금흐름 차이"),
    404: ("스트레스 테스트", "스트레스테스트", "최악의 경우", "가정 점검"),
    405: ("사이클", "경기 순환", "국면 판단", "사이클 판단"),
    406: ("dcf", "현금흐름할인", "내재가치 계산", "미래 현금흐름"),
    407: ("해자", "경쟁 우위", "moat", "진입 장벽", "브랜드 파워"),
    408: ("자본배분", "경영진 자질", "재투자", "주주가치"),
    409: ("레버리지 리스크", "고부채", "금리 상승 위험", "이자 부담"),
    410: ("수급", "vix", "공포지수", "시장 심리", "외국인 매수"),
    # T5 상급
    501: ("독립적인 논리", "내 논리", "스스로 판단", "남 따라"),
    502: ("프레임워크", "틀 조합", "여러 기준", "복합 판단"),
    503: ("리스크 관리", "손실 관리", "최대 비중", "규칙"),
    504: ("시장 맥락", "시장 흐름", "큰 그림", "전체 문맥"),
    505: ("복기", "실수 점검", "왜 틀렸는지", "자기 점검"),
    506: ("포지션 관리", "수익 포지션", "익절 기준", "보유 판단"),
    507: ("확증 편향", "인지 편향", "편향", "심리적 오류"),
    508: ("유동성", "거래량 적은", "소형주", "매도 어려움"),
    509: ("알파", "초과 수익", "시장 대비", "정보 우위"),
    510: ("성과 분석", "수익률 복기", "운이었나", "실력 검증"),
}


def keywords_for_concept(concept_id: int) -> tuple[str, ...]:
    """개념 id의 채팅 인식 트리거 키워드. 일일 리포트가 멘토 질문에 이 키워드를
    심어, 사용자가 질문을 보내면 같은 개념의 팔로우업 퀴즈가 발생하도록 한다."""
    return _CONCEPT_KEYWORDS.get(concept_id, ())


def recommend_quiz_for_text(
    tier: Tier,
    text: str,
    solved_question_ids: set[str] | frozenset[str],
) -> TierQuiz | None:
    matched_concept_ids = _rank_matched_concepts(tier, text)
    if not matched_concept_ids:
        return None

    quizzes = list_tier_quizzes(tier)
    for concept_id in matched_concept_ids:
        concept_quizzes = [
            quiz
            for quiz in quizzes
            if quiz.concept_id == concept_id and quiz.question_id not in solved_question_ids
        ]
        if concept_quizzes:
            return concept_quizzes[0]

    return None


def _rank_matched_concepts(tier: Tier, text: str) -> list[int]:
    normalized = _normalize(text)
    if not normalized:
        return []

    scored: list[tuple[int, int]] = []
    for concept in list_concepts_for_tier(tier):
        score = 0
        for keyword in _CONCEPT_KEYWORDS.get(concept.id, ()):
            if _normalize(keyword) in normalized:
                score += 2 if len(keyword) >= 4 else 1
        if score > 0:
            scored.append((concept.id, score))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return [concept_id for concept_id, _score in scored]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "")


__all__ = ["keywords_for_concept", "recommend_quiz_for_text"]
