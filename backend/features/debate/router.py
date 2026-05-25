"""4동 — 토론 (투기장).

owner: TODO
관련 FR: FR-04, UC-03
**중요**: ADR-011 — core/ai_pipeline의 빌딩블록 직접 사용. features/learning import 금지.
페르소나는 토론 동 자체 정의 또는 core/contracts에 공용 등재.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from core.ai_pipeline import RAGContext, guardrail, rag
from core.ai_pipeline.news_search import news_search
from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.contracts import DebateCompletedEvent, DebateSessionId, Tier, UserId
from core.db import get_db
from core.event_bus import event_bus
from core.exceptions import (
    BadRequestError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    ForbiddenError,
    NotFoundError,
)
from core.user_context import user_context
from core.vector_store import Document
from features.debate.models import DebateMessage, DebateSession
from features.debate.personas import (
    DEFAULT_PERSONA_A,
    DEFAULT_PERSONA_B,
    DebatePersona,
    get_persona,
    has_persona,
    list_personas,
)
from features.debate import service as debate_service

router = APIRouter(prefix="/api/debate", tags=["debate"])
logger = logging.getLogger("debate")


class DebateStartRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=255)
    persona_a_id: str = DEFAULT_PERSONA_A
    persona_b_id: str = DEFAULT_PERSONA_B


class DebateStartResponse(BaseModel):
    debate_session_id: int
    topic: str
    status: str
    stream_url: str


class DebatePersonaResponse(BaseModel):
    id: str
    name: str
    stance: str
    style: str
    is_public: bool


class DebateEligibilityResponse(BaseModel):
    allowed: bool
    tier: str
    reason: str | None = None


async def _ensure_debate_allowed(user_id: UserId) -> Tier:
    tier = await user_context.get_tier(user_id)
    if tier == Tier.T1:
        raise ForbiddenError("투기장은 T2부터 활성화됩니다 (BR-01)")
    return tier


@router.get("/eligibility")
async def eligibility(user: User = Depends(get_current_user)) -> DebateEligibilityResponse:
    # BR-01: 투기장 기능은 T2 이상 사용자에게만 활성화된다
    tier = await user_context.get_tier(UserId(user.id))
    if tier == Tier.T1:
        return DebateEligibilityResponse(
            allowed=False,
            tier=tier.value,
            reason="투기장은 T2부터 활성화됩니다 (BR-01)",
        )
    return DebateEligibilityResponse(allowed=True, tier=tier.value)


@router.get("/personas")
async def personas(user: User = Depends(get_current_user)) -> list[DebatePersonaResponse]:
    await _ensure_debate_allowed(UserId(user.id))
    return [DebatePersonaResponse(**p.__dict__) for p in list_personas(include_system=True)]


@router.post("/start")
async def start_debate(
    req: DebateStartRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DebateStartResponse:
    await _ensure_debate_allowed(UserId(user.id))
    raw_topic = req.topic.strip()
    if not raw_topic:
        raise BadRequestError("토론 주제를 입력해야 합니다.")
    input_check = guardrail.check_input(raw_topic)
    if not input_check.ok:
        raise BadRequestError(input_check.reason)
    if _is_lifestyle_choice_topic(raw_topic):
        raise BadRequestError("투기장은 투자·경제·산업 관련 주제로만 토론할 수 있습니다.")
    topic = await _extract_debate_topic(raw_topic)
    if not _is_investment_topic(topic):
        raise BadRequestError("투기장은 투자·경제·산업 관련 주제로만 토론할 수 있습니다.")
    if not has_persona(req.persona_a_id) or not has_persona(req.persona_b_id):
        raise BadRequestError("Unknown debate persona")
    if req.persona_a_id == req.persona_b_id:
        raise BadRequestError("서로 다른 두 토론 페르소나를 선택해야 합니다.")

    session = DebateSession(
        user_id=user.id,
        topic=topic,
        persona_a_id=req.persona_a_id,
        persona_b_id=req.persona_b_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return DebateStartResponse(
        debate_session_id=session.id,
        topic=session.topic,
        status=session.status,
        stream_url=f"/api/debate/{session.id}/stream",
    )


@router.get("/{debate_session_id}/stream")
async def stream_debate(
    debate_session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    await _ensure_debate_allowed(UserId(user.id))
    session = await _get_session(db, debate_session_id, user.id)
    if session.status == "streaming":
        raise ConflictError("Debate session is already streaming")
    if session.status == "failed":
        raise ConflictError("Debate session failed. Please start a new debate session")

    async def event_gen() -> AsyncIterator[dict[str, str]]:
        if session.status == "completed":
            async for event in _replay_session(db, session):
                yield event
            return

        try:
            session.status = "streaming"
            session.error_message = None
            await db.commit()

            rag_ctx = await _retrieve_context(session.topic)
            yield _event(
                "context",
                {
                    "debate_session_id": session.id,
                    "documents": [_document_payload(doc) for doc in rag_ctx.documents],
                },
            )
            turns = [
                (
                    1,
                    get_persona(session.persona_a_id),
                    "opinion",
                    "주제에 대한 첫 의견을 제시하세요.",
                ),
                (
                    2,
                    get_persona(session.persona_b_id),
                    "rebuttal",
                    "앞선 의견의 허점을 반박하고 다른 관점을 제시하세요.",
                ),
                (
                    3,
                    get_persona(session.persona_a_id),
                    "counter",
                    "반박을 받아들이되, 최종 재반박과 균형 잡힌 결론을 제시하세요.",
                ),
            ]
            history: list[str] = []
            debate_script = await debate_service.generate_script(session.topic, turns, rag_ctx)
            script_generation_failed = debate_script is None
            debate_script = debate_script or {}

            for turn_index, persona, turn_type, instruction in turns:
                yield _event(
                    "turn_start",
                    {
                        "turn_index": turn_index,
                        "turn_type": turn_type,
                        "speaker": _persona_payload(persona),
                    },
                )
                scripted_turn = debate_script.get(turn_index)
                answer = scripted_turn.content if scripted_turn else None
                if answer is None:
                    if script_generation_failed:
                        answer = debate_service.fallback_turn(
                            session.topic,
                            persona,
                            turn_type,
                            rag_ctx,
                            history,
                        )
                    else:
                        answer = await debate_service.generate_turn_answer(
                            session.topic,
                            persona,
                            turn_type,
                            instruction,
                            rag_ctx,
                            history,
                        )
                checked, critic_result = await debate_service.check_answer(answer, persona, rag_ctx)

                message = DebateMessage(
                    debate_session_id=session.id,
                    turn_index=turn_index,
                    speaker_id=persona.id,
                    turn_type=turn_type,
                    content=checked,
                    critic_result=critic_result.model_dump() if critic_result else None,
                )
                db.add(message)
                await db.commit()
                history.append(f"{persona.name}: {checked}")

                async for event in _stream_text(turn_index, persona, checked):
                    yield event
                yield _event("turn_done", {"turn_index": turn_index})

            session.status = "completed"
            session.completed_at = datetime.now(UTC)
            await db.commit()
            await event_bus.publish(
                DebateCompletedEvent(
                    user_id=UserId(user.id),
                    debate_session_id=DebateSessionId(session.id),
                )
            )
            yield _event("done", {"debate_session_id": session.id})
        except DomainError as exc:
            await _mark_session_failed(db, session, exc.message)
            logger.warning(
                "debate.stream_failed",
                extra={
                    "debate_session_id": session.id,
                    "code": exc.code,
                    "error_message": exc.message,
                },
            )
            yield _event(
                "error",
                {
                    "debate_session_id": session.id,
                    "code": exc.code,
                    "message": _public_stream_error_message(exc),
                },
            )
        except asyncio.CancelledError:
            await _mark_session_failed(db, session, "토론 스트림 연결이 중단되었습니다.")
            logger.warning(
                "debate.stream_cancelled",
                extra={"debate_session_id": session.id},
            )
            raise
        except Exception:
            await _mark_session_failed(db, session, "토론 생성 중 오류가 발생했습니다.")
            logger.exception(
                "debate.stream_unhandled_error",
                extra={"debate_session_id": session.id},
            )
            yield _event(
                "error",
                {
                    "debate_session_id": session.id,
                    "code": "internal_error",
                    "message": "토론 생성 중 오류가 발생했습니다.",
                },
            )

    return EventSourceResponse(event_gen())


def _public_stream_error_message(exc: DomainError) -> str:
    if isinstance(exc, ExternalServiceError):
        return "토론 생성 서비스가 아직 준비되지 않았습니다. 잠시 후 다시 시도해 주세요."
    return exc.message


async def _get_session(db: AsyncSession, debate_session_id: int, user_id: int) -> DebateSession:
    session = await db.get(DebateSession, debate_session_id)
    if session is None or session.user_id != user_id:
        raise NotFoundError("Debate session not found")
    return session


async def _mark_session_failed(
    db: AsyncSession,
    session: DebateSession,
    message: str,
) -> None:
    session.status = "failed"
    session.error_message = message[:255]
    await db.commit()


async def _replay_session(
    db: AsyncSession,
    session: DebateSession,
) -> AsyncIterator[dict[str, str]]:
    result = await db.execute(
        select(DebateMessage)
        .where(DebateMessage.debate_session_id == session.id)
        .order_by(DebateMessage.turn_index)
    )
    for message in result.scalars():
        persona = get_persona(message.speaker_id)
        yield _event(
            "turn_start",
            {
                "turn_index": message.turn_index,
                "turn_type": message.turn_type,
                "speaker": _persona_payload(persona),
                "replay": True,
            },
        )
        async for event in _stream_text(message.turn_index, persona, message.content):
            yield event
        yield _event("turn_done", {"turn_index": message.turn_index, "replay": True})
    yield _event("done", {"debate_session_id": session.id, "replay": True})


async def _retrieve_context(topic: str) -> RAGContext:
    documents = []
    try:
        rag_context = await rag.retrieve(topic, collection="investment_knowledge", top_k=4)
        documents.extend(rag_context.documents)
    except ExternalServiceError:
        pass

    if len(documents) < 2:
        try:
            documents.extend(await _search_news_documents(topic))
        except ExternalServiceError:
            pass

    return RAGContext(documents=_dedupe_documents(documents), query=topic)


async def _search_news_documents(topic: str) -> list[Document]:
    documents: list[Document] = []
    for query in _news_queries(topic):
        documents.extend(await news_search.search(query, top_k=2))
    relevant = _filter_topic_documents(topic, _dedupe_documents(documents))
    return _sort_recent_documents(relevant)[:5]


def _news_queries(topic: str) -> list[str]:
    keywords = _topic_keywords(topic)
    base = " ".join(keywords) if keywords else topic
    topic_type = _classify_topic(topic)
    if topic_type == "macro":
        macro_queries = _macro_news_queries(topic, base)
        if macro_queries:
            return _unique_preserve_order(macro_queries)
    if topic_type == "theme":
        theme_queries = _theme_news_queries(topic, base)
        if theme_queries:
            return _unique_preserve_order(theme_queries)
    if topic_type == "stock":
        company_queries = _company_news_queries(topic, base)
        if company_queries:
            return _unique_preserve_order(company_queries)
        return _unique_preserve_order(
            [
                base,
                f"{base} 실적 전망",
                f"{base} 주가 밸류에이션",
                f"{base} 수급 리스크",
                f"{base} 최신 뉴스",
                f"{base} 오늘",
            ]
        )
    return _unique_preserve_order(
        [
            base,
            f"{base} 최신 뉴스",
            f"{base} 오늘",
            f"{base} 실적 전망",
            f"{base} 투자 리스크",
            f"{base} 밸류에이션",
            f"{base} 수급 모멘텀",
        ]
    )


def _classify_topic(topic: str) -> str:
    compact = topic.lower()
    if re.search(r"금리|연준|fomc|환율|물가|인플레이션|cpi|고용|유가|원유|채권", compact):
        return "macro"
    if _has_company_mention(compact):
        return "stock"
    if re.search(r"비트코인|이더리움|가상자산|암호화폐|\bbtc\b|\beth\b", compact, re.IGNORECASE):
        return "theme"
    if re.search(
        r"\bai\b|인공지능|반도체|2차전지|배터리|전기차|데이터센터|클라우드|전력|원전|방산|조선|바이오|로봇|게임|엔터",
        compact,
        re.IGNORECASE,
    ):
        return "theme"
    return "general"


def _has_company_mention(topic: str) -> bool:
    if re.search(
        r"삼성전자|하이닉스|엔비디아|애플|테슬라|현대차|네이버|카카오|구글|알파벳|메타|아마존|마이크로소프트|오픈AI|오픈ai|(?<![A-Za-z])nvidia(?![A-Za-z])|(?<![A-Za-z])nvda(?![A-Za-z])|(?<![A-Za-z])openai(?![A-Za-z])|(?<![A-Za-z])microsoft(?![A-Za-z])|(?<![A-Za-z])msft(?![A-Za-z])|(?<![A-Za-z])google(?![A-Za-z])|(?<![A-Za-z])googl?(?![A-Za-z])|(?<![A-Za-z])alphabet(?![A-Za-z])|(?<![A-Za-z])meta(?![A-Za-z])|(?<![A-Za-z])amazon(?![A-Za-z])|(?<![A-Za-z])amzn(?![A-Za-z])|(?<![A-Za-z])amd(?![A-Za-z])|(?<![A-Za-z])apple(?![A-Za-z])|(?<![A-Za-z])aapl(?![A-Za-z])|(?<![A-Za-z])tesla(?![A-Za-z])|(?<![A-Za-z])tsla(?![A-Za-z])",
        topic,
        re.IGNORECASE,
    ):
        return True
    return False


def _is_investment_topic(topic: str) -> bool:
    compact = topic.lower()
    if _classify_topic(topic) in {"macro", "theme", "stock"}:
        return True
    return bool(
        re.search(
            r"주식|증시|코스피|코스닥|나스닥|s&p|투자|매수|매도|실적|주가|밸류에이션|per|pbr|"
            r"배당|수급|모멘텀|리스크|오너리스크|전망|산업|업황|경기|경제|기업|성장|현금흐름|환율|금리|코인|가상자산|암호화폐",
            compact,
            re.IGNORECASE,
        )
    )


def _is_lifestyle_choice_topic(text: str) -> bool:
    compact = text.lower()
    if _has_explicit_investment_intent(compact):
        return False
    lifestyle_terms = (
        r"먹|마시|점심|저녁|아침|야식|메뉴|맛집|식당|카페|커피|버거|햄버거|치킨|피자|"
        r"라면|떡볶이|맥도날드|버거킹|롯데리아|맘스터치|스타벅스|메가커피|컴포즈|"
        r"입을까|살까\s+말까|데이트|영화|여행|운동"
    )
    choice_terms = r"먹을까|마실까|갈까|고를까|뭐\s*먹|뭐\s*마시|뭐\s*하지|vs|VS|중에|또는|아니면"
    return bool(re.search(lifestyle_terms, compact) and re.search(choice_terms, compact))


def _has_explicit_investment_intent(text: str) -> bool:
    return bool(
        re.search(
            r"주식|증시|투자|매수|매도|주가|실적|밸류에이션|per|pbr|배당|수급|포트폴리오|종목|기업가치",
            text,
            re.IGNORECASE,
        )
    )


def _macro_news_queries(topic: str, base: str) -> list[str]:
    compact = topic.lower()
    if "물가" in topic or "인플레이션" in compact or "cpi" in compact:
        if "성장주" in topic:
            return [
                "CPI 상승 성장주 밸류에이션 부담",
                "인플레이션 금리 성장주 영향",
                "물가 지표 성장주 가치주 비교",
                "연준 금리 전망 성장주 투자 리스크",
            ]
        return [
            "물가 인플레이션 주식시장 영향",
            "CPI 금리 전망 한국 증시",
            "인플레이션 성장주 가치주 영향",
            "물가 투자 리스크",
        ]
    if "금리" in topic or "연준" in topic or "fomc" in compact:
        if "인하" in topic:
            return [
                "금리 인하 주식시장 영향",
                "금리 인하 성장주 가치주 영향",
                "연준 금리 인하 전망 한국 증시",
                "금리 인하 환율 외국인 수급",
                "금리 인하 밸류에이션 투자 리스크",
            ]
        if "상승" in topic or "인상" in topic:
            return [
                "금리 상승 주식시장 영향",
                "금리 상승 성장주 밸류에이션 부담",
                "채권금리 상승 한국 증시",
                "금리 상승 환율 외국인 수급",
                "금리 상승 투자 리스크",
            ]
        return [
            "금리 전망 주식시장 영향",
            "연준 FOMC 한국 증시 영향",
            "금리 변화 성장주 가치주 영향",
            "금리 환율 외국인 수급",
            f"{base} 투자 리스크",
        ]
    if "환율" in topic:
        return [
            "환율 변화 한국 증시 영향",
            "원달러 환율 외국인 수급",
            "환율 상승 수출주 내수주 영향",
            "환율 투자 리스크",
        ]
    if "유가" in topic or "원유" in topic:
        if "항공" in topic:
            return [
                "유가 변화 항공주 수익성 영향",
                "항공주 유류비 실적 전망",
                "국제유가 항공업 투자 리스크",
                "유가 환율 항공주 수급",
            ]
        return [
            "국제유가 상승 업종별 영향",
            "유가 변화 인플레이션 금리 전망",
            "유가 수혜주 피해주",
            "유가 투자 리스크",
        ]
    return []


def _company_news_queries(topic: str, base: str) -> list[str]:
    compact = topic.lower()
    if ("amd" in compact or "AMD" in topic) and (
        "nvidia" in compact or "nvda" in compact or "엔비디아" in topic
    ):
        return [
            "AMD Nvidia AI 반도체 경쟁 구도",
            "AMD AI 가속기 시장 점유율",
            "Nvidia 데이터센터 GPU 경쟁 리스크",
            "AI 반도체 수요 실적 전망",
        ]
    if "openai" in compact and ("오너리스크" in topic or "리스크" in topic):
        return [
            "OpenAI 샘 올트먼 지배구조 리스크",
            "OpenAI 경영진 리스크 투자",
            "OpenAI 지분구조 오너리스크",
            "OpenAI Microsoft 투자 리스크",
            "OpenAI 거버넌스 이슈",
        ]
    if "openai" in compact:
        return [
            "OpenAI 투자 전망",
            "OpenAI Microsoft 협력 리스크",
            "OpenAI 매출 성장 전망",
            "OpenAI 경쟁 구도",
        ]
    if "nvidia" in compact or "nvda" in compact or "엔비디아" in topic:
        return [
            "Nvidia 실적 전망 AI 반도체 수요",
            "Nvidia 주가 밸류에이션 리스크",
            "Nvidia 데이터센터 매출 전망",
            "Nvidia 중국 수출 규제 리스크",
            "Nvidia 경쟁 구도 AMD ASIC",
        ]
    company = _canonical_company_name(topic)
    if company:
        prefix = [company] if base == company else []
        recency = [f"{company} 오늘"] if base == company else []
        return [
            *prefix,
            f"{company} 실적 전망",
            f"{company} 주가 밸류에이션",
            f"{company} 성장 리스크",
            f"{company} 최신 뉴스",
            *recency,
            f"{company} 경쟁 구도",
        ]
    return []


def _theme_news_queries(topic: str, base: str) -> list[str]:
    compact = topic.lower()
    if "비트코인" in topic or "btc" in compact:
        return [
            "비트코인 가격 전망 금리 유동성",
            "비트코인 ETF 자금 유입",
            "비트코인 규제 리스크",
            "가상자산 시장 변동성",
        ]
    if "이더리움" in topic or "eth" in compact:
        return [
            "이더리움 가격 전망",
            "이더리움 ETF 자금 유입",
            "이더리움 네트워크 수수료 리스크",
            "가상자산 시장 변동성",
        ]
    if re.search(r"\bai\b|인공지능|반도체|데이터센터|클라우드", compact, re.IGNORECASE):
        return [
            "AI 투자 거품 밸류에이션",
            "AI 반도체 수요 실적 전망",
            "AI 인프라 투자 수익성 리스크",
            f"{base} 최신 뉴스",
            _risk_query(base),
        ]
    if "전기차" in topic and "2차전지" not in topic and "배터리" not in topic:
        return [
            "전기차 판매 둔화 수요 회복 전망",
            "전기차 시장 수익성 경쟁 리스크",
            "전기차 배터리 가격 소비자 수요",
            f"{base} 최신 뉴스",
            _risk_query(base),
        ]
    if "2차전지" in topic or "배터리" in topic:
        return [
            "2차전지 전기차 수요 회복 전망",
            "배터리 소재 가격 수익성 리스크",
            "전기차 판매 둔화 2차전지 실적",
            f"{base} 최신 뉴스",
            _risk_query(base),
        ]
    if "원전" in topic or "전력" in topic:
        return [
            "전력 수요 증가 원전 투자 전망",
            "원전 수주 정책 리스크",
            "전력 인프라 투자 수익성",
            f"{base} 최신 뉴스",
        ]
    if "방산" in topic or "조선" in topic:
        subject = "방산" if "방산" in topic else "조선"
        return [
            f"{subject} 수주 실적 전망",
            f"{subject} 환율 원가 리스크",
            f"{subject} 밸류에이션 투자 리스크",
            f"{subject} 최신 뉴스",
        ]
    if "게임" in topic or "엔터" in topic or "바이오" in topic or "로봇" in topic:
        subject = _theme_subject(topic)
        return [
            f"{subject} 산업 전망",
            f"{subject} 실적 전망",
            f"{subject} 밸류에이션 리스크",
            f"{subject} 최신 뉴스",
        ]
    return [
        f"{base} 산업 전망",
        f"{base} 실적 전망",
        f"{base} 밸류에이션 리스크",
        f"{base} 최신 뉴스",
    ]


def _risk_query(base: str) -> str:
    return f"{base} 리스크 요인" if "리스크" not in base else f"{base} 핵심 쟁점"


def _canonical_company_name(topic: str) -> str:
    compact = topic.lower()
    pairs = [
        ("삼성전자", r"삼성전자"),
        ("SK하이닉스", r"하이닉스"),
        ("애플", r"애플|(?<![A-Za-z])apple(?![A-Za-z])|(?<![A-Za-z])aapl(?![A-Za-z])"),
        ("테슬라", r"테슬라|(?<![A-Za-z])tesla(?![A-Za-z])|(?<![A-Za-z])tsla(?![A-Za-z])"),
        ("현대차", r"현대차"),
        ("네이버", r"네이버"),
        ("카카오", r"카카오"),
        ("마이크로소프트", r"마이크로소프트|(?<![A-Za-z])microsoft(?![A-Za-z])|(?<![A-Za-z])msft(?![A-Za-z])"),
        ("구글", r"구글|알파벳|(?<![A-Za-z])google(?![A-Za-z])|(?<![A-Za-z])googl?(?![A-Za-z])|(?<![A-Za-z])alphabet(?![A-Za-z])"),
        ("메타", r"메타|(?<![A-Za-z])meta(?![A-Za-z])"),
        ("아마존", r"아마존|(?<![A-Za-z])amazon(?![A-Za-z])|(?<![A-Za-z])amzn(?![A-Za-z])"),
        ("AMD", r"(?<![A-Za-z])amd(?![A-Za-z])"),
    ]
    for label, pattern in pairs:
        if re.search(pattern, compact, re.IGNORECASE):
            return label
    return ""


def _theme_subject(topic: str) -> str:
    for subject in ["게임", "엔터", "바이오", "로봇"]:
        if subject in topic:
            return subject
    return _topic_keywords(topic, limit=1)[0] if _topic_keywords(topic, limit=1) else topic


def _topic_keywords(topic: str, limit: int = 4) -> list[str]:
    cleaned = re.sub(r"[^\w가-힣\s]", " ", topic)
    stopwords = {
        "지금",
        "사야",
        "할까",
        "투자할까",
        "하나",
        "살까",
        "팔까",
        "뭐",
        "투자",
        "판단",
        "전략",
        "영향",
        "시장",
        "주식시장",
        "주식",
        "기업가치",
        "미치는",
        "다시",
        "될까",
        "봐도",
        "끝난",
        "건가",
        "괜찮",
        "관련",
        "대해",
        "어떻게",
        "좋을까",
        "괜찮을까",
        "거품",
        "거품인가",
        "뉴스",
        "최신",
        "오늘",
    }
    keywords: list[str] = []
    for token in cleaned.split():
        raw_token = token.strip(" ,./;:，。")
        if raw_token in stopwords:
            continue
        token = _clean_keyword_token(token)
        if len(token) < 2 or token in stopwords:
            continue
        keywords.append(token)
    if not keywords and topic.strip():
        keywords.append(topic.strip())
    return _unique_preserve_order(keywords)[:limit]


def _clean_keyword_token(token: str) -> str:
    clean = token.strip(" ,./;:，。")
    if clean.endswith(("인가", "일까", "될까")):
        return clean
    clean = re.sub(r"(으로|에서|에게|부터|까지|처럼|보다|하고|이며)$", "", clean)
    clean = re.sub(r"(은|는|이|가|을|를|에|로|와|과|도|만|의)$", "", clean)
    return clean


def _strong_topic_keywords(topic: str) -> list[str]:
    generic = {"주식", "투자", "전략", "판단", "영향", "시장", "관련"}
    return [keyword for keyword in _topic_keywords(topic, limit=6) if keyword not in generic]


def _filter_topic_documents(topic: str, documents: list[Document]) -> list[Document]:
    keywords = _strong_topic_keywords(topic)
    if not keywords:
        return documents

    matched = [
        doc
        for doc in documents
        if _document_matches_keywords(doc, keywords)
        and not debate_service.is_low_signal_news(
            str(doc.metadata.get("title") or doc.metadata.get("headline") or ""),
            str(doc.metadata.get("source") or ""),
            str(doc.metadata.get("url") or ""),
        )
    ]
    return matched or documents


def _document_matches_keywords(doc: Document, keywords: list[str]) -> bool:
    haystack = " ".join(
        [
            doc.text,
            str(doc.metadata.get("title") or ""),
            str(doc.metadata.get("headline") or ""),
            str(doc.metadata.get("source") or ""),
        ]
    ).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _unique_preserve_order(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return unique


def _dedupe_documents(documents: list[Document]) -> list[Document]:
    deduped: list[Document] = []
    seen: set[str] = set()
    for doc in documents:
        key = str(doc.metadata.get("url") or doc.id or doc.text[:80])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
    return deduped


def _sort_recent_documents(documents: list[Document]) -> list[Document]:
    return sorted(documents, key=_published_timestamp, reverse=True)


def _published_timestamp(doc: Document) -> float:
    value = str(doc.metadata.get("published_at") or "").strip()
    if not value:
        return 0.0
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


async def _extract_debate_topic(user_input: str) -> str:
    fallback_topic = _fallback_extract_debate_topic(user_input)
    if len(fallback_topic) >= 2 and _topic_keywords(fallback_topic):
        return fallback_topic

    refined_topic = await debate_service.refine_topic(user_input)
    if refined_topic:
        return _normalize_debate_topic(refined_topic)

    if len(fallback_topic) < 2:
        raise BadRequestError("토론 주제를 입력해야 합니다.")
    return fallback_topic


def _clean_extracted_topic(text: str) -> str:
    topic = text.strip().splitlines()[0] if text.strip() else ""
    topic = re.sub(r"^[\-*•\d.)\s]+", "", topic)
    topic = re.sub(r"^(토론\s*)?주제\s*[:：]\s*", "", topic)
    topic = topic.strip(" \"'“”‘’`")
    topic = re.sub(r"\s+", " ", topic)
    return _normalize_debate_topic(topic[:80].strip())


def _fallback_extract_debate_topic(user_input: str) -> str:
    topic = user_input.strip()
    topic = re.sub(r"[\"'“”‘’`]", "", topic)
    topic = re.sub(r"[!?？！]+", " ", topic)
    topic = re.sub(r"\b(요즘|최근|지금|혹시|그럼|나는|내가|제가|좀|진짜)\b", " ", topic)
    topic = re.sub(r"(계속|많이|너무|막)\s+", " ", topic)
    topic = re.sub(r"(금리|기준금리)\s*(내리|내려가|인하하)(면|면은)?", r"\1 인하 ", topic)
    topic = re.sub(r"(금리|채권금리)\s*(오르|올라가|상승하)(면|면은)?", r"\1 상승 ", topic)
    topic = re.sub(r"(떨어지|하락하|내려가)(면|면은)?", "하락 ", topic)
    topic = re.sub(r"(오르|올라가|상승하)(면|면은)?", "상승 ", topic)
    topic = re.sub(r"(높|높아지|낮|낮아지)(으면|면|면은)?", "변화 ", topic)
    topic = re.sub(r"(떨어지|오르|올라가|내려가|흔들리)(고|는데|는\s*중인데)?", " ", topic)
    topic = re.sub(r"(사야|살까|매수해야)\s*(할까|하나|돼|되는지|괜찮을까)?", "투자", topic)
    topic = re.sub(r"(사도|매수해도|들어가도)\s*(될까|돼|되는지|괜찮을까)?", "투자", topic)
    topic = re.sub(r"(팔아야|매도해야)\s*(할까|하나|될까|돼|되는지|하는지|괜찮을까|괜찮아)?", "매도 판단", topic)
    topic = re.sub(r"장기(로)?\s*투자(해도|하면)?\s*(될까|돼|되는지|괜찮을까|괜찮아)?", "장기 투자", topic)
    topic = re.sub(r"투자(해도|하면)?\s*(될까|돼|되는지|괜찮을까|괜찮아)?", "투자", topic)
    topic = re.sub(
        r"(투자|매도 판단)(?=(?!할까|해도|하면|돼|되는지|괜찮)[A-Za-z가-힣0-9])",
        r"\1 ",
        topic,
    )
    topic = re.sub(
        r"(에\s*대해(서)?|관련해서|가지고)?\s*(토론|토의|얘기|이야기|대화)\s*(해줘|해|하자|해볼래|하고\s*싶어)?",
        " ",
        topic,
    )
    topic = re.sub(r"(어떻게\s*생각해|어떻게\s*해|어떡해|어때|괜찮을까|괜찮아|좋을까|알려줘|말해줘)", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" ,./;:，。")
    topic = re.sub(r"\s+(은|는|이|가|을|를|에|으로|로)$", "", topic)
    topic = re.sub(r"(영향|전망|리스크|전략)(은|는)$", r"\1", topic)
    return _normalize_debate_topic(topic[:80].strip())


def _normalize_debate_topic(topic: str) -> str:
    compact = re.sub(r"\s+", " ", topic).strip(" ,./;:，。")
    lower_compact = compact.lower()
    if not compact:
        return compact
    comparison_topic = _normalize_investment_comparison_topic(compact)
    if comparison_topic:
        return comparison_topic
    topic_type = _classify_topic(compact)
    if topic_type == "theme":
        return _normalize_theme_topic(compact)
    if topic_type != "macro":
        return compact
    if "금리" in compact and "인하" in compact and ("영향" in compact or "증시" in compact or "주식시장" in compact):
        return "금리 인하가 주식시장과 기업가치에 미치는 영향"
    if "금리" in compact and ("상승" in compact or "인상" in compact) and (
        "영향" in compact or "증시" in compact or "주식시장" in compact
    ):
        return "금리 상승이 주식시장과 기업가치에 미치는 영향"
    if "환율" in compact and "영향" in compact:
        return "환율 변화가 주식시장과 기업 실적에 미치는 영향"
    if "환율" in compact and ("상승" in compact or "하락" in compact):
        return "환율 변화가 투자 판단에 미치는 영향"
    if ("cpi" in lower_compact or "물가" in compact or "인플레이션" in compact) and (
        "변화" in compact or "상승" in compact or "하락" in compact
    ):
        return "물가 변화가 금리와 성장주 밸류에이션에 미치는 영향"
    if ("cpi" in lower_compact or "물가" in compact or "인플레이션" in compact) and "성장주" in compact:
        return "물가 변화가 금리와 성장주 밸류에이션에 미치는 영향"
    if "유가" in compact or "원유" in compact:
        if "항공" in compact:
            return "유가 변화가 항공주 수익성에 미치는 영향"
        return "유가 변화가 업종별 수익성에 미치는 영향"
    if ("물가" in compact or "인플레이션" in compact) and "영향" in compact:
        return "물가 변화가 금리와 주식시장에 미치는 영향"
    return compact


def _normalize_investment_comparison_topic(topic: str) -> str:
    if len(re.findall(r"(?<![A-Za-z가-힣0-9])투자(?![A-Za-z가-힣0-9])", topic)) < 2:
        return ""
    parts = [
        part.strip(" ,./;:，。")
        for part in re.split(r"\s+(?:투자)\s+", f" {topic} ")
        if part.strip(" ,./;:，。")
    ]
    if len(parts) < 2:
        return ""
    candidates = [_clean_comparison_subject(part) for part in parts[:2]]
    if any(len(candidate) < 2 for candidate in candidates):
        return ""
    if candidates[0] == candidates[1]:
        return f"{candidates[0]} 투자"
    return f"{candidates[0]}와 {candidates[1]} 투자 비교"


def _clean_comparison_subject(text: str) -> str:
    clean = re.sub(r"\b(vs|VS)\b", " ", text)
    clean = re.sub(r"(중에|또는|아니면)$", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" ,./;:，。")
    return clean


def _normalize_theme_topic(topic: str) -> str:
    compact = re.sub(r"\s+", " ", topic).strip(" ,./;:，。")
    if re.search(r"\bAI\b|인공지능", compact, re.IGNORECASE) and "거품" in compact:
        return "AI 주식의 밸류에이션 부담과 성장 지속성"
    if "2차전지" in compact or "배터리" in compact:
        if "장기" in compact:
            return "2차전지 장기 성장성과 투자 리스크"
        if re.search(r"다시|회복|봐도|될까|괜찮", compact):
            return "2차전지 수요 회복과 투자 리스크"
        return "2차전지 산업 전망과 투자 리스크"
    if "전기차" in compact:
        if re.search(r"끝난|둔화|부진|망", compact):
            return "전기차 시장 둔화와 회복 가능성"
        return "전기차 시장 성장성과 수익성 리스크"
    if "원전" in compact or "전력" in compact:
        return "전력 수요 증가와 원전 투자 리스크"
    if "방산" in compact:
        return "방산 수주 성장성과 밸류에이션 리스크"
    if "조선" in compact:
        return "조선업 수주 사이클과 실적 지속성"
    return compact


def _document_payload(doc: Document) -> dict[str, object]:
    title = str(doc.metadata.get("title") or doc.metadata.get("headline") or "").strip()
    return {
        "id": doc.id,
        "title": title,
        "source": str(doc.metadata.get("source") or "").strip(),
        "url": str(doc.metadata.get("url") or "").strip(),
        "published_at": str(doc.metadata.get("published_at") or "").strip(),
        "metadata": doc.metadata,
    }

async def _stream_text(
    turn_index: int,
    persona: DebatePersona,
    text: str,
) -> AsyncIterator[dict[str, str]]:
    for chunk in text.split(" "):
        yield _event(
            "delta",
            {
                "turn_index": turn_index,
                "speaker": _persona_payload(persona),
                "delta": chunk + " ",
            },
        )
        await asyncio.sleep(0.02)


def _event(event: str, payload: dict[str, object]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False)}


def _persona_payload(persona: DebatePersona) -> dict[str, str]:
    return {"id": persona.id, "name": persona.name}
