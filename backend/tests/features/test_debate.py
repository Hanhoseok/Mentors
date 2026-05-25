import importlib
from types import SimpleNamespace

import pytest

from core.ai_pipeline import RAGContext
from core.contracts import Tier
from core.vector_store import Document
from features.debate.models import DebateMessage, DebateSession

debate_router = importlib.import_module("features.debate.router")
debate_service = importlib.import_module("features.debate.service")
debate_mentor_ai = importlib.import_module("features.debate.mentor_ai")
debate_personas = importlib.import_module("features.debate.personas")


class FakeStartDB:
    def __init__(self) -> None:
        self.session: DebateSession | None = None

    def add(self, obj: DebateSession) -> None:
        self.session = obj
        obj.id = 123
        obj.status = obj.status or "created"

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: DebateSession) -> None:
        pass


class FakeStreamDB:
    def __init__(self) -> None:
        self.session = DebateSession(
            id=123,
            user_id=1,
            topic="금리 상승기 성장주 전략",
            persona_a_id="value",
            persona_b_id="growth",
            status="created",
        )
        self.messages: list[DebateMessage] = []

    async def get(self, model: type[DebateSession], obj_id: int) -> DebateSession:
        return self.session

    def add(self, obj: DebateMessage) -> None:
        self.messages.append(obj)

    async def commit(self) -> None:
        pass


@pytest.fixture(autouse=True)
def debate_t2_user(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_tier(user_id: int) -> Tier:
        return Tier.T2

    monkeypatch.setattr(debate_router.user_context, "get_tier", fake_tier)


async def test_start_debate_creates_session() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic=" 금리 상승기 성장주 전략 "),
        SimpleNamespace(id=1),
        db,
    )

    assert response.debate_session_id == 123
    assert response.topic == "금리 상승기 성장주 전략"
    assert response.status == "created"
    assert response.stream_url == "/api/debate/123/stream"
    assert db.session is not None
    assert db.session.persona_a_id == "value"
    assert db.session.persona_b_id == "growth"


async def test_start_debate_extracts_topic_from_colloquial_input() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(
            topic="요즘 2차전지 계속 떨어지는데 장기로 투자해도 될까 토론해줘"
        ),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "2차전지 장기 성장성과 투자 리스크"
    assert db.session is not None
    assert db.session.topic == "2차전지 장기 성장성과 투자 리스크"


async def test_start_debate_extracts_buy_question_as_neutral_topic() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="삼성전자 지금 사도 될까 토론해줘"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "삼성전자 투자"


async def test_start_debate_normalizes_macro_question_without_hurting_stock_topic() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="금리 인하 영향은?"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "금리 인하가 주식시장과 기업가치에 미치는 영향"


async def test_start_debate_normalizes_exchange_rate_buy_question() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="달러 환율 오르면 뭐 사야 돼?"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "환율 변화가 투자 판단에 미치는 영향"


async def test_start_debate_accepts_english_company_outlook_topic() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="nvidia 전망"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "nvidia 전망"


@pytest.mark.parametrize(
    ("raw_topic", "expected_topic"),
    [
        ("CPI 높으면 성장주 어떡해?", "물가 변화가 금리와 성장주 밸류에이션에 미치는 영향"),
        ("유가 오르면 항공주는?", "유가 변화가 항공주 수익성에 미치는 영향"),
        ("비트코인 지금 어때", "비트코인"),
        ("메타 지금 괜찮나", "메타 괜찮나"),
        ("MSFT 실적 전망", "MSFT 실적 전망"),
        ("연준이 금리 내리면 한국 증시는 어떻게 돼?", "금리 인하가 주식시장과 기업가치에 미치는 영향"),
        ("원달러 환율이 계속 올라가면 수출주는 유리해?", "환율 변화가 투자 판단에 미치는 영향"),
        ("애플 실적 부진해도 장기투자 괜찮아?", "애플 실적 부진해도 장기 투자"),
    ],
)
async def test_start_debate_accepts_broad_investment_input_types(
    raw_topic: str,
    expected_topic: str,
) -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic=raw_topic),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == expected_topic


async def test_start_debate_normalizes_ai_bubble_question() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="AI 주식 거품인가"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "AI 주식의 밸류에이션 부담과 성장 지속성"


async def test_start_debate_normalizes_battery_reentry_question() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="2차전지 다시 봐도 될까"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "2차전지 수요 회복과 투자 리스크"


async def test_start_debate_normalizes_ev_slowdown_question() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="전기차 시장 끝난 건가"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "전기차 시장 둔화와 회복 가능성"


async def test_start_debate_rejects_non_investment_topic() -> None:
    db = FakeStartDB()

    with pytest.raises(debate_router.BadRequestError) as exc:
        await debate_router.start_debate(
            debate_router.DebateStartRequest(topic="점심 뭐 먹지"),
            SimpleNamespace(id=1),
            db,
        )

    assert "투자·경제·산업" in exc.value.message
    assert db.session is None


@pytest.mark.parametrize(
    "topic",
    [
        "맥도날드 먹을까 버거킹 먹을까?",
        "스타벅스 갈까 메가커피 갈까?",
    ],
)
async def test_start_debate_rejects_lifestyle_brand_choice(topic: str) -> None:
    db = FakeStartDB()

    with pytest.raises(debate_router.BadRequestError) as exc:
        await debate_router.start_debate(
            debate_router.DebateStartRequest(topic=topic),
            SimpleNamespace(id=1),
            db,
        )

    assert "투자·경제·산업" in exc.value.message
    assert db.session is None


async def test_start_debate_allows_ambiguous_buy_word_for_user_convenience() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="맥도날드 살까 버거킹 살까?"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "맥도날드와 버거킹 투자 비교"


async def test_start_debate_normalizes_stock_comparison_question() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="삼성전자 살까 하이닉스 살까?"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "삼성전자와 하이닉스 투자 비교"


async def test_start_debate_allows_brand_when_investment_intent_is_explicit() -> None:
    db = FakeStartDB()

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="맥도날드 주식 투자할까"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "맥도날드 주식 투자할까"


async def test_start_debate_uses_local_topic_extraction_before_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeStartDB()
    called = False

    async def fake_chat(*args: object, **kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("topic extraction should not call llm for simple inputs")

    monkeypatch.setattr(debate_mentor_ai.llm, "chat", fake_chat)

    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic="삼성전자 지금 사도 될까 토론해줘"),
        SimpleNamespace(id=1),
        db,
    )

    assert response.topic == "삼성전자 투자"
    assert called is False


async def test_start_debate_accepts_two_public_debate_mentors() -> None:
    db = FakeStartDB()
    response = await debate_router.start_debate(
        debate_router.DebateStartRequest(
            topic="소비재 성장주 평가",
            persona_a_id="dividend",
            persona_b_id="momentum",
        ),
        SimpleNamespace(id=1),
        db,
    )

    assert response.debate_session_id == 123
    assert db.session is not None
    assert db.session.persona_a_id == "dividend"
    assert db.session.persona_b_id == "momentum"


async def test_eligibility_returns_not_allowed_for_t1(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_tier(user_id: int) -> Tier:
        return Tier.T1

    monkeypatch.setattr(debate_router.user_context, "get_tier", fake_tier)

    response = await debate_router.eligibility(SimpleNamespace(id=1))

    assert response.allowed is False
    assert response.tier == "T1"
    assert response.reason is not None


async def test_retrieve_context_uses_news_when_rag_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_rag(query: str, collection: str, top_k: int) -> RAGContext:
        return RAGContext(documents=[], query=query)

    async def fake_news(query: str, top_k: int) -> list[Document]:
        return [
            Document(
                id="news_1",
                text="배당주 장기 투자에 대한 최근 분석이다.",
                metadata={"source": "test-news", "title": "배당주 분석"},
            )
        ]

    monkeypatch.setattr(debate_router.rag, "retrieve", fake_rag)
    monkeypatch.setattr(debate_router.news_search, "search", fake_news)

    context = await debate_router._retrieve_context("배당주 장기 투자")

    assert len(context.documents) == 1
    assert context.documents[0].metadata["source"] == "test-news"


async def test_fallback_turn_uses_news_evidence_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = RAGContext(
        documents=[
            Document(
                id="news_1",
                text=(
                    "AI 반도체 수요가 클라우드 설비 투자 확대로 이어지고 있다. "
                    "공급망 병목은 부담이다."
                ),
                metadata={"source": "sample-news", "title": "AI 인프라 투자 확대"},
            )
        ],
        query="AI 반도체 장기 투자",
    )
    monkeypatch.setattr(debate_mentor_ai, "is_llm_ready", lambda: False)

    answer = await debate_service.generate_turn_answer(
        "AI 반도체 장기 투자",
        debate_personas.get_persona("value"),
        "opinion",
        "주제에 대한 첫 의견을 제시하세요.",
        context,
        [],
    )

    assert "AI 반도체 수요" in answer
    assert '"AI 인프라 투자 확대"(sample-news)' in answer
    assert "실제 현금흐름과 주주환원 여력" in answer


def test_news_evidence_uses_description_instead_of_repeated_title() -> None:
    context = RAGContext(
        documents=[
            Document(
                id="news_1",
                text=(
                    "DRAM 폭등 소식에 흔들렸다… 지금 삼성전자 사야 할까? - example.com. "
                    "메모리 가격 반등이 실적 기대를 키우고 있지만 밸류에이션 부담은 남아 있다."
                ),
                metadata={
                    "source": "example.com",
                    "title": "DRAM 폭등 소식에 흔들렸다… 지금 삼성전자 사야 할까? - example.com",
                    "url": "https://example.com/news",
                },
            )
        ],
        query="삼성전자 투자",
    )

    evidence = debate_service.extract_news_evidence(context)

    assert len(evidence) == 1
    assert evidence[0].title.startswith("DRAM 폭등")
    assert evidence[0].sentence == "메모리 가격 반등이 실적 기대를 키우고 있지만 밸류에이션 부담은 남아 있다"
    assert "메모리 가격 반등" in evidence[0].as_text()


def test_news_evidence_summarizes_question_style_title_when_description_is_missing() -> None:
    context = RAGContext(
        documents=[
            Document(
                id="news_1",
                text="삼성전자·SK하이닉스, 지금이라도 사야 하나 - 미디어펜.",
                metadata={
                    "source": "미디어펜",
                    "title": "삼성전자·SK하이닉스, 지금이라도 사야 하나 - 미디어펜",
                    "url": "https://example.com/news",
                },
            )
        ],
        query="삼성전자 투자",
    )

    evidence = debate_service.extract_news_evidence(context)

    assert evidence[0].sentence == "삼성전자와 반도체주의 매수 타이밍이 투자자들의 핵심 쟁점으로 다뤄지고 있다"
    assert "사야 하나라는 점" not in evidence[0].as_text()


def test_news_evidence_summarizes_headline_style_sentence_without_description() -> None:
    context = RAGContext(
        documents=[
            Document(
                id="news_1",
                text="반도체·AI 폭등 장세…월스트리트의 5가지 폭락 대비법 - 네이트.",
                metadata={
                    "source": "네이트",
                    "title": "반도체·AI 폭등 장세…월스트리트의 5가지 폭락 대비법 - 네이트",
                    "url": "https://example.com/news",
                },
            )
        ],
        query="AI 주식 거품인가",
    )

    evidence = debate_service.extract_news_evidence(context)

    assert evidence[0].sentence == "AI 관련 주식의 가격 상승 기대와 조정 우려가 함께 부각되고 있다"
    assert "폭락 대비법 네이트라는 점" not in evidence[0].as_text()


def test_news_evidence_summarizes_macro_title_without_source_tail() -> None:
    context = RAGContext(
        documents=[
            Document(
                id="news_1",
                text="미국 연방준비제도 금리 인하 이유와 추가 인하 전망, 한국 영향 총정리 🇺🇸💰🇰🇷 - 뉴닉.",
                metadata={
                    "source": "뉴닉",
                    "title": "미국 연방준비제도 금리 인하 이유와 추가 인하 전망, 한국 영향 총정리 🇺🇸💰🇰🇷 - 뉴닉",
                    "url": "https://example.com/news",
                },
            )
        ],
        query="금리 인하가 주식시장과 기업가치에 미치는 영향",
    )

    evidence = debate_service.extract_news_evidence(context)

    assert evidence[0].sentence == "금리 인하 기대가 할인율, 성장주 밸류에이션, 환율과 수급 판단에 영향을 주고 있다"
    assert "뉴닉라는 점" not in evidence[0].as_text()
    assert "🇺🇸" not in evidence[0].as_prompt_line()


def test_news_evidence_ignores_domain_tail_from_repeated_title() -> None:
    context = RAGContext(
        documents=[
            Document(
                id="news_1",
                text=(
                    "DRAM 폭등 소식에 흔들렸다… 지금 삼성전자 사야 할까? "
                    "개인투자자의 현실 경험담 - fathomjournal.org."
                ),
                metadata={
                    "source": "fathomjournal.org",
                    "title": (
                        "DRAM 폭등 소식에 흔들렸다… 지금 삼성전자 사야 할까? "
                        "개인투자자의 현실 경험담 - fathomjournal.org"
                    ),
                    "url": "https://example.com/news",
                },
            ),
            Document(
                id="news_2",
                text="삼성전자·SK하이닉스, 지금이라도 사야 하나 - 미디어펜.",
                metadata={
                    "source": "미디어펜",
                    "title": "삼성전자·SK하이닉스, 지금이라도 사야 하나 - 미디어펜",
                    "url": "https://example.com/news2",
                },
            ),
        ],
        query="삼성전자 투자",
    )

    evidence = debate_service.extract_news_evidence(context)

    assert len(evidence) == 1
    assert evidence[0].sentence == "삼성전자와 반도체주의 매수 타이밍이 투자자들의 핵심 쟁점으로 다뤄지고 있다"
    assert "fathomjournal.org라는 점" not in evidence[0].as_text()


def test_news_evidence_marks_aggressive_forecasts_as_speculative() -> None:
    context = RAGContext(
        documents=[
            Document(
                id="news_1",
                text="삼성전자 48만원 간다…2026년 영업이익 372조 전망.",
                metadata={
                    "source": "sample-news",
                    "title": "삼성전자 48만원 간다…'2026년 영업이익 372조' 전망",
                    "url": "https://example.com/news",
                },
            )
        ],
        query="삼성전자 투자",
    )

    evidence = debate_service.extract_news_evidence(context)
    prompt_line = evidence[0].as_prompt_line()

    assert evidence[0].is_speculative is True
    assert "주의:" in prompt_line
    assert "확정 사실이 아니라 시장 기대" in prompt_line


async def test_generate_turn_uses_llm_when_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = RAGContext(
        documents=[
            Document(
                id="news_1",
                text="AI 인프라 투자가 늘고 있지만 공급망 병목이 변수로 남아 있다.",
                metadata={"source": "sample-news", "title": "AI 인프라 투자 확대"},
            )
        ],
        query="AI 반도체 장기 투자",
    )
    llm_answer = "AI 인프라 투자가 늘어난 점은 긍정적입니다. 다만 공급망 병목이 남아 있어 실적 지속성을 확인해야 합니다."
    seen_prompt = ""

    async def fake_chat(messages: list[object], temperature: float, max_tokens: int) -> object:
        nonlocal seen_prompt
        seen_prompt = messages[-1].content
        return SimpleNamespace(text=llm_answer)

    monkeypatch.setattr(debate_mentor_ai, "is_llm_ready", lambda: True)
    monkeypatch.setattr(debate_mentor_ai.llm, "chat", fake_chat)

    answer = await debate_service.generate_turn_answer(
        "AI 반도체 장기 투자",
        debate_personas.get_persona("value"),
        "opinion",
        "주제에 대한 첫 의견을 제시하세요.",
        context,
        [],
    )

    assert answer == llm_answer
    assert "한국어 자연문 3~5문장" in seen_prompt
    assert "220자 이내" not in seen_prompt
    assert "반드시 자료에서 나온 사실 1개" not in seen_prompt


def test_news_queries_use_topic_keywords_instead_of_raw_question() -> None:
    queries = debate_router._news_queries("삼성전자 지금 사야 할까")

    assert queries[0] == "삼성전자"
    assert all("사야 할까" not in query for query in queries)
    assert "삼성전자 최신 뉴스" in queries
    assert "삼성전자 오늘" in queries
    assert "삼성전자 실적 전망" in queries


def test_news_queries_remove_investment_question_suffix() -> None:
    queries = debate_router._news_queries("맥도날드 주식 투자할까")

    assert queries[0] == "맥도날드"
    assert all("투자할까" not in query for query in queries)


def test_openai_owner_risk_queries_use_governance_context() -> None:
    queries = debate_router._news_queries("openai의 오너리스크")

    assert queries[0] == "OpenAI 샘 올트먼 지배구조 리스크"
    assert "OpenAI Microsoft 투자 리스크" in queries


def test_nvidia_outlook_queries_use_ai_semiconductor_context() -> None:
    queries = debate_router._news_queries("nvidia 전망")

    assert queries[0] == "Nvidia 실적 전망 AI 반도체 수요"
    assert "Nvidia 주가 밸류에이션 리스크" in queries


@pytest.mark.parametrize(
    ("topic", "expected_first"),
    [
        ("MSFT 실적 전망", "마이크로소프트 실적 전망"),
        ("구글 전망", "구글 실적 전망"),
        ("메타 괜찮나", "메타 실적 전망"),
        ("아마존 주가 전망", "아마존 실적 전망"),
        ("비트코인", "비트코인 가격 전망 금리 유동성"),
        ("유가 변화가 항공주 수익성에 미치는 영향", "유가 변화 항공주 수익성 영향"),
        ("물가 변화가 금리와 성장주 밸류에이션에 미치는 영향", "CPI 상승 성장주 밸류에이션 부담"),
        ("애플 실적 부진해도 장기 투자", "애플 실적 전망"),
        ("테슬라 주가 오른 것 같은데 투자", "테슬라 실적 전망"),
        ("구글 AI 투자 때문에 마진 안 좋아질까", "구글 실적 전망"),
        ("AMD가 엔비디아 따라잡을 수 있을까", "AMD Nvidia AI 반도체 경쟁 구도"),
    ],
)
def test_news_queries_cover_aliases_crypto_and_oil(
    topic: str,
    expected_first: str,
) -> None:
    queries = debate_router._news_queries(topic)

    assert queries[0] == expected_first


def test_macro_news_queries_are_investment_specific() -> None:
    queries = debate_router._news_queries("금리 인하가 주식시장과 기업가치에 미치는 영향")

    assert queries[0] == "금리 인하 주식시장 영향"
    assert "금리 인하 성장주 가치주 영향" in queries
    assert all("영향은" not in query for query in queries)


def test_topic_keywords_strip_korean_particles_from_macro_topic() -> None:
    keywords = debate_router._topic_keywords("금리 인하가 주식시장과 기업가치에 미치는 영향", limit=6)

    assert "금리" in keywords
    assert "인하" in keywords
    assert "주식시장" not in keywords
    assert "인하가" not in keywords
    assert "기업가치에" not in keywords


def test_theme_news_queries_focus_on_investment_context() -> None:
    queries = debate_router._news_queries("AI 주식 거품인가")

    assert queries[0] == "AI 투자 거품 밸류에이션"
    assert "AI 반도체 수요 실적 전망" in queries
    assert "AI 인프라 투자 수익성 리스크" in queries
    assert all("거품인가" not in query for query in queries)
    assert all("거품인" not in query for query in queries)


def test_battery_theme_news_queries_cover_demand_and_profitability() -> None:
    queries = debate_router._news_queries("2차전지 다시 봐도 될까")

    assert queries[0] == "2차전지 전기차 수요 회복 전망"
    assert "배터리 소재 가격 수익성 리스크" in queries
    assert "전기차 판매 둔화 2차전지 실적" in queries
    assert all("다시 될까" not in query for query in queries)


def test_theme_news_queries_do_not_duplicate_risk_terms() -> None:
    queries = debate_router._news_queries("2차전지 수요 회복과 투자 리스크")

    assert all("투자 리스크 투자 리스크" not in query for query in queries)
    assert "2차전지 수요 회복 리스크 핵심 쟁점" in queries


def test_ev_theme_news_queries_do_not_collapse_into_battery_only() -> None:
    queries = debate_router._news_queries("전기차 시장 둔화와 회복 가능성")

    assert queries[0] == "전기차 판매 둔화 수요 회복 전망"
    assert "전기차 시장 수익성 경쟁 리스크" in queries
    assert "전기차 배터리 가격 소비자 수요" in queries


def test_low_signal_news_filters_community_and_video_sources() -> None:
    assert debate_service.is_low_signal_news(
        "AI 주식 개인 투자자 현실 경험담",
        "블로그",
        "https://example.com/post",
    )
    assert debate_service.is_low_signal_news(
        "삼성전자 투자 전망",
        "YouTube",
        "https://youtube.com/watch?v=abc",
    )
    assert debate_service.is_low_signal_news(
        "카카오 나가고 하나은행 들어왔다…네이버·두나무 빅딜 '탄력' - jabon.co.kr",
        "jabon.co.kr",
        "https://news.google.com/rss/articles/example",
    )
    assert debate_service.is_low_signal_news(
        "카카오 투자분석 - 주달",
        "주달",
        "https://news.google.com/rss/articles/example",
    )
    assert debate_service.is_low_signal_news(
        "카카오뱅크의 플랫폼 독주와 AX 혁신 -> 증권·투신사 유동성 독점하는 중개 허브 - 데일리머니",
        "데일리머니",
        "https://news.google.com/rss/articles/example",
    )


def test_news_reference_uses_shortened_title_without_source_tail() -> None:
    evidence = debate_service.NewsEvidence(
        title="미국 연방준비제도 금리 인하 이유와 추가 인하 전망, 한국 영향 총정리 🇺🇸💰🇰🇷 | 네이버 뉴스",
        source="네이버 뉴스",
        url="https://example.com/news",
        sentence="금리 인하 기대가 성장주 밸류에이션과 환율 판단에 영향을 주고 있다",
    )

    reference = debate_service.natural_news_reference(evidence)

    assert "네이버 뉴스" not in reference.split("\"", maxsplit=2)[1]
    assert "🇺🇸" not in reference
    assert len(reference.split("\"", maxsplit=2)[1]) <= 45
    assert "다는 점입니다" not in reference
    assert "영향을 주는 흐름을 확인할 수 있습니다" in reference


def test_news_reference_summarizes_kakao_title_naturally() -> None:
    sentence = debate_service.summarize_news_title(
        "카카오 나가고 하나은행 들어왔다…네이버·두나무 빅딜 '탄력' - jabon.co.kr"
    )
    evidence = debate_service.NewsEvidence(
        title="카카오 나가고 하나은행 들어왔다…네이버·두나무 빅딜 '탄력' - jabon.co.kr",
        source="jabon.co.kr",
        url="https://example.com/news",
        sentence=sentence,
    )

    reference = debate_service.natural_news_reference(evidence)

    assert sentence == "카카오 관련 지분과 사업 재편 이슈가 투자 판단의 변수로 부각되고 있다"
    assert "jabon.co.kr" not in reference.split("\"", maxsplit=2)[1]
    assert "부각되는 흐름을 확인할 수 있습니다" in reference


def test_sort_recent_documents_orders_by_published_at() -> None:
    old = Document(
        id="old",
        text="old",
        metadata={"published_at": "Wed, 20 May 2026 09:26:00 GMT"},
    )
    new = Document(
        id="new",
        text="new",
        metadata={"published_at": "Thu, 21 May 2026 05:43:11 GMT"},
    )
    unknown = Document(id="unknown", text="unknown", metadata={})

    sorted_docs = debate_router._sort_recent_documents([old, unknown, new])

    assert [doc.id for doc in sorted_docs] == ["new", "old", "unknown"]


def test_filter_topic_documents_prefers_strong_topic_match() -> None:
    ai_doc = Document(
        id="ai",
        text="AI 관련 주식의 가격 부담과 성장 기대가 함께 커지고 있다.",
        metadata={"title": "AI 거품 경고 현실화되나"},
    )
    unrelated_doc = Document(
        id="lg",
        text="LG전자 기업평판과 주가 흐름을 분석한다.",
        metadata={"title": "어매이징 LG전자, 지금은 거품일까?"},
    )

    filtered = debate_router._filter_topic_documents("AI 주식 거품인가", [unrelated_doc, ai_doc])

    assert [doc.id for doc in filtered] == ["ai"]


def test_parse_debate_script_reads_three_turns() -> None:
    text = """
    ```json
    {"core_issue":"실적 회복 기대와 가격 반영 정도의 충돌","bullish_evidence":["메모리 가격 상승"],"bearish_evidence":["법적 리스크"],"uncertainties":["전망치 신뢰도"],"turns":[
      {"turn_index":1,"claim":"실적 기대보다 현금흐름 지속성을 확인해야 한다","balanced_view":"실적 기대는 긍정적이지만 가격 반영은 확인해야 한다","uses_evidence":["법적 리스크"],"content":"뉴스 흐름을 보면 실적 기대가 살아나는 점은 분명합니다. 다만 배당 관점에서는 현금흐름의 지속성을 더 봐야 합니다."},
      {"turn_index":2,"responds_to":"현금흐름 지속성을 먼저 확인해야 한다는 주장","agreement":"현금흐름 확인은 필요하다","counterpoint":"메모리 가격 상승이 실적 추정을 빠르게 바꿀 수 있다","uses_evidence":["메모리 가격 상승"],"content":"그 말은 맞지만 성장 관점에서는 변화 속도도 중요합니다. 실적 기대가 올라가는 국면이라면 프리미엄을 일부 설명할 수 있습니다."},
      {"turn_index":3,"responds_to":"메모리 가격 상승이 실적 추정을 바꿀 수 있다는 주장","agreement":"업황 회복은 긍정적이다","counterpoint":"그 기대가 현재 가격에 얼마나 반영됐는지 확인해야 한다","uses_evidence":["전망치 신뢰도"],"content":"그래도 가격에 기대가 얼마나 반영됐는지는 분리해서 봐야 합니다. 다음 실적에서 현금흐름과 주주환원이 같이 확인되는지가 핵심입니다."}
    ]}
    ```
    """

    parsed = debate_service.parse_debate_script(text)

    assert set(parsed) == {1, 2, 3}
    assert "현금흐름" in parsed[1].content
    assert parsed[1].claim == "실적 기대보다 현금흐름 지속성을 확인해야 한다"
    assert parsed[1].balanced_view == "실적 기대는 긍정적이지만 가격 반영은 확인해야 한다"
    assert parsed[2].responds_to == "현금흐름 지속성을 먼저 확인해야 한다는 주장"
    assert parsed[2].agreement == "현금흐름 확인은 필요하다"
    assert parsed[3].counterpoint == "그 기대가 현재 가격에 얼마나 반영됐는지 확인해야 한다"


def test_parse_debate_script_reads_json_with_surrounding_text() -> None:
    text = """
    아래 JSON으로 작성했습니다.

    {
      "core_issue": "가격과 실적",
      "turns": [
        {"turn_index": 1, "content": "좋게 볼 부분은 있지만 가격 부담도 같이 봐야 합니다. 그래서 현금흐름 확인이 필요합니다."},
        {"turn_index": 2, "content": "현금흐름 확인이 필요하다는 점은 동의합니다. 다만 실적 추정이 빠르게 바뀌는 구간도 놓치면 안 됩니다."},
        {"turn_index": 3, "content": "실적 추정 변화는 인정합니다. 그래도 그 기대가 주가에 얼마나 반영됐는지 확인해야 합니다."}
      ]
    }

    참고하세요.
    """

    parsed = debate_service.parse_debate_script(text)

    assert set(parsed) == {1, 2, 3}
    assert "가격 부담" in parsed[1].content


def test_parse_debate_script_tolerates_trailing_commas_and_extra_text() -> None:
    text = """
    ```JSON
    {
      "turns": [
        {"turn_index": 1, "content": "첫 의견은 신중해야 합니다. 그래도 확인할 장점은 있습니다. 현재 가격에 기대가 얼마나 반영됐는지 함께 봐야 합니다."},
        {"turn_index": 2, "content": "그 신중론은 맞습니다. 다만 성장 가능성도 함께 봐야 합니다. 시장 규모가 빠르게 커진다면 일부 프리미엄은 설명될 수 있습니다."},
        {"turn_index": 3, "content": "성장 가능성은 인정합니다. 하지만 현금흐름으로 증명돼야 합니다. 기대가 실제 이익으로 바뀌는지 확인하는 과정이 필요합니다."},
      ],
    }
    ```
    """

    parsed = debate_service.parse_debate_script(text)

    assert set(parsed) == {1, 2, 3}


def test_parse_debate_script_accepts_turn_array_root() -> None:
    text = """
    [
      {"turn_index": 1, "content": "첫 의견은 신중해야 합니다. 그래도 확인할 장점은 있습니다. 가격 부담도 함께 봐야 합니다."},
      {"turn_index": 2, "content": "그 신중론은 맞습니다. 다만 성장 가능성도 함께 봐야 합니다. 변화 속도를 놓치면 안 됩니다."},
      {"turn_index": 3, "content": "성장 가능성은 인정합니다. 그래도 현금흐름으로 증명되는지 확인해야 합니다. 기대가 실제 이익으로 바뀌는 과정이 필요합니다."}
    ]
    """

    parsed = debate_service.parse_debate_script(text)

    assert set(parsed) == {1, 2, 3}


async def test_generate_debate_script_requires_all_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(*args: object, **kwargs: object) -> object:
        return SimpleNamespace(
            text=(
                '{"turns": ['
                '{"turn_index": 1, "content": "첫 의견은 신중해야 합니다. 그래도 확인할 장점은 있습니다. 가격 부담도 함께 봐야 합니다."}'
                ']}'
            )
        )

    turns = [
        (1, debate_personas.get_persona("value"), "opinion", "첫 의견"),
        (2, debate_personas.get_persona("growth"), "rebuttal", "반박"),
        (3, debate_personas.get_persona("value"), "counter", "재반박"),
    ]

    monkeypatch.setattr(debate_mentor_ai, "is_llm_ready", lambda: True)
    monkeypatch.setattr(debate_mentor_ai.llm, "chat", fake_chat)

    parsed = await debate_service.generate_script(
        "AI 주식 거품인가",
        turns,
        RAGContext(documents=[], query="AI 주식 거품인가"),
    )

    assert parsed is None


async def test_generate_debate_script_repairs_incomplete_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_chat(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            return SimpleNamespace(
                text='{"turns":[{"turn_index":1,"content":"첫 의견은 신중해야 합니다. 그래도 확인할 장점은 있습니다. 가격 부담도 함께 봐야 합니다."}]}'
            )
        return SimpleNamespace(
            text=(
                '{"turns":['
                '{"turn_index":1,"content":"첫 의견은 신중해야 합니다. 그래도 확인할 장점은 있습니다. 가격 부담도 함께 봐야 합니다."},'
                '{"turn_index":2,"content":"그 신중론은 맞습니다. 다만 성장 가능성도 함께 봐야 합니다. 변화 속도를 놓치면 안 됩니다."},'
                '{"turn_index":3,"content":"성장 가능성은 인정합니다. 그래도 현금흐름으로 증명되는지 확인해야 합니다. 기대가 실제 이익으로 바뀌는 과정이 필요합니다."}'
                "]}"
            )
        )

    turns = [
        (1, debate_personas.get_persona("value"), "opinion", "첫 의견"),
        (2, debate_personas.get_persona("growth"), "rebuttal", "반박"),
        (3, debate_personas.get_persona("value"), "counter", "재반박"),
    ]

    monkeypatch.setattr(debate_mentor_ai.llm, "chat", fake_chat)

    parsed = await debate_service.generate_script(
        "AI 주식 거품인가",
        turns,
        RAGContext(documents=[], query="AI 주식 거품인가"),
    )

    assert parsed is not None
    assert set(parsed) == {1, 2, 3}
    assert calls == 2


async def test_script_parse_failure_does_not_call_turn_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_context(topic: str) -> RAGContext:
        return RAGContext(documents=[], query=topic)

    async def broken_script(topic: str, turns: list[object], context: RAGContext) -> None:
        return None

    async def fail_generate(*args: object, **kwargs: object) -> str:
        raise AssertionError("turn-level LLM should not run after script parse failure")

    monkeypatch.setattr(debate_router, "_retrieve_context", fake_context)
    monkeypatch.setattr(debate_service, "generate_script", broken_script)
    monkeypatch.setattr(debate_service, "generate_turn_answer", fail_generate)

    db = FakeStreamDB()
    response = await debate_router.stream_debate(123, SimpleNamespace(id=1), db)

    events = [item["event"] async for item in response.body_iterator]

    assert events[-1] == "done"
    assert len(db.messages) == 3
    assert all("확인된 참고 자료가 부족합니다" in message.content for message in db.messages[:1])


async def test_stream_debate_generates_three_turns_and_publishes_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_context(topic: str) -> RAGContext:
        return RAGContext(documents=[], query=topic)

    async def fake_generate(
        topic: str,
        persona: object,
        turn_type: str,
        instruction: str,
        context: RAGContext,
        history: list[str],
    ) -> str:
        return f"{persona.name} test turn"

    published: list[tuple[str, int]] = []

    async def fake_publish(event: object) -> None:
        published.append((event.event_type, int(event.debate_session_id)))

    async def no_script(topic: str, turns: list[object], context: RAGContext) -> dict[int, str]:
        return {}

    monkeypatch.setattr(debate_router, "_retrieve_context", fake_context)
    monkeypatch.setattr(debate_service, "generate_script", no_script)
    monkeypatch.setattr(debate_service, "generate_turn_answer", fake_generate)
    monkeypatch.setattr(debate_router.event_bus, "publish", fake_publish)

    db = FakeStreamDB()
    response = await debate_router.stream_debate(123, SimpleNamespace(id=1), db)

    events: list[str] = []
    async for item in response.body_iterator:
        events.append(item["event"])

    assert events[0] == "context"
    assert events.count("turn_start") == 3
    assert events.count("turn_done") == 3
    assert events[-1] == "done"
    assert len(db.messages) == 3
    assert db.session.status == "completed"
    assert published == [("debate.completed", 123)]


async def test_stream_debate_rejects_already_streaming_session() -> None:
    db = FakeStreamDB()
    db.session.status = "streaming"

    with pytest.raises(debate_router.ConflictError):
        await debate_router.stream_debate(123, SimpleNamespace(id=1), db)


async def test_stream_debate_marks_failed_and_emits_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_context(topic: str) -> RAGContext:
        raise debate_router.ExternalServiceError("vector store unavailable")

    monkeypatch.setattr(debate_router, "_retrieve_context", fail_context)

    db = FakeStreamDB()
    response = await debate_router.stream_debate(123, SimpleNamespace(id=1), db)

    events: list[dict[str, str]] = []
    async for item in response.body_iterator:
        events.append(item)

    assert events[-1]["event"] == "error"
    assert "토론 생성 서비스가 아직 준비되지 않았습니다" in events[-1]["data"]
    assert db.session.status == "failed"
    assert db.session.error_message == "vector store unavailable"
