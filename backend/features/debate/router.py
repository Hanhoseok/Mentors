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
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from core.ai_pipeline import RAGContext, critic, guardrail, hallucination, rag
from core.ai_pipeline.critic import CriticResult
from core.ai_pipeline.news_search import news_search
from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.contracts import DebateCompletedEvent, DebateSessionId, MessageRole, Tier, UserId
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
from core.llm import Message, llm
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

router = APIRouter(prefix="/api/debate", tags=["debate"])
logger = logging.getLogger("debate")


@dataclass(frozen=True)
class DebateScriptTurn:
    turn_index: int
    content: str
    claim: str = ""
    balanced_view: str = ""
    agreement: str = ""
    responds_to: str = ""
    counterpoint: str = ""
    uses_evidence: tuple[str, ...] = ()


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
    topic = await _extract_debate_topic(raw_topic)
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
            debate_script = await _generate_debate_script(session.topic, turns, rag_ctx)
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
                        answer = _fallback_turn(session.topic, persona, turn_type, rag_ctx, history)
                    else:
                        answer = await _generate_turn(
                            session.topic,
                            persona,
                            turn_type,
                            instruction,
                            rag_ctx,
                            history,
                        )
                checked, critic_result = await _check_answer(answer, persona, rag_ctx)

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


def _topic_keywords(topic: str, limit: int = 4) -> list[str]:
    cleaned = re.sub(r"[^\w가-힣\s]", " ", topic)
    stopwords = {
        "지금",
        "사야",
        "할까",
        "하나",
        "살까",
        "팔까",
        "투자",
        "판단",
        "전략",
        "영향",
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
        token = token.strip()
        if len(token) < 2 or token in stopwords:
            continue
        keywords.append(token)
    if not keywords and topic.strip():
        keywords.append(topic.strip())
    return _unique_preserve_order(keywords)[:limit]


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
        and not _is_low_signal_news(
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

    if llm.configured:
        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=(
                    "사용자의 구어체 요청에서 투자 토론 주제만 추출합니다. "
                    "명령, 감탄, 질문 어미, '토론해줘' 같은 요청 표현은 제거하세요. "
                    "출력은 한국어 명사구 하나만, 2~40자, 따옴표와 설명 없이 작성하세요."
                ),
            ),
            Message(role=MessageRole.USER, content=user_input),
        ]
        try:
            response = await llm.chat(messages, temperature=0.0, max_tokens=80)
            topic = _clean_extracted_topic(response.text)
            if len(topic) >= 2:
                return topic
        except ExternalServiceError:
            pass

    if len(fallback_topic) < 2:
        raise BadRequestError("토론 주제를 입력해야 합니다.")
    return fallback_topic


def _clean_extracted_topic(text: str) -> str:
    topic = text.strip().splitlines()[0] if text.strip() else ""
    topic = re.sub(r"^[\-*•\d.)\s]+", "", topic)
    topic = re.sub(r"^(토론\s*)?주제\s*[:：]\s*", "", topic)
    topic = topic.strip(" \"'“”‘’`")
    topic = re.sub(r"\s+", " ", topic)
    return topic[:80].strip()


def _fallback_extract_debate_topic(user_input: str) -> str:
    topic = user_input.strip()
    topic = re.sub(r"[\"'“”‘’`]", "", topic)
    topic = re.sub(r"[!?？！]+", " ", topic)
    topic = re.sub(r"\b(요즘|최근|지금|혹시|그럼|나는|내가|제가|좀|진짜)\b", " ", topic)
    topic = re.sub(r"(계속|많이|너무|막)\s+", " ", topic)
    topic = re.sub(r"(떨어지|오르|흔들리)(고|는데|는\s*중인데)?", " ", topic)
    topic = re.sub(r"(사야|살까|매수해야)\s*(할까|하나|돼|되는지|괜찮을까)?", "투자", topic)
    topic = re.sub(r"(사도|매수해도|들어가도)\s*(될까|돼|되는지|괜찮을까)?", "투자", topic)
    topic = re.sub(r"(팔아야|매도해야)\s*(할까|될까|돼|하는지)?", "매도 판단", topic)
    topic = re.sub(r"장기(로)?\s*투자(해도|하면)?\s*(될까|돼|되는지|괜찮을까)?", "장기 투자", topic)
    topic = re.sub(r"투자(해도|하면)?\s*(될까|돼|되는지|괜찮을까)?", "투자", topic)
    topic = re.sub(
        r"(에\s*대해(서)?|관련해서|가지고)?\s*(토론|토의|얘기|이야기|대화)\s*(해줘|해|하자|해볼래|하고\s*싶어)?",
        " ",
        topic,
    )
    topic = re.sub(r"(어떻게\s*생각해|어때|괜찮을까|좋을까|알려줘|말해줘)", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" ,./;:，。")
    topic = re.sub(r"\s+(은|는|이|가|을|를|에|으로|로)$", "", topic)
    return topic[:80].strip()


async def _generate_turn(
    topic: str,
    persona: DebatePersona,
    turn_type: str,
    instruction: str,
    context: RAGContext,
    history: list[str],
) -> str:
    if not _is_llm_ready():
        return _fallback_turn(topic, persona, turn_type, context, history)

    messages = _build_turn_messages(topic, persona, instruction, context, history)
    try:
        response = await llm.chat(messages, temperature=0.45, max_tokens=700)
        answer = response.text.strip()
        if _needs_turn_retry(answer):
            retry_messages = [
                *messages,
                Message(
                    role=MessageRole.ASSISTANT,
                    content=answer or "응답이 비어 있습니다.",
                ),
                Message(
                    role=MessageRole.USER,
                    content=(
                        "방금 응답은 토론 발화로 쓰기에는 너무 짧거나 완성된 문장이 아닙니다. "
                        "뉴스 근거를 1개 이상 반영해 한국어 완성 문장 2~4개로 다시 작성하세요. "
                        "제목, 명사구, 요약어가 아니라 멘토가 실제로 말하는 발화여야 합니다."
                    ),
                ),
            ]
            response = await llm.chat(retry_messages, temperature=0.35, max_tokens=700)
            answer = response.text.strip()
        if _needs_turn_retry(answer):
            fallback_draft = _fallback_turn(topic, persona, turn_type, context, history)
            repair_messages = [
                Message(role=MessageRole.SYSTEM, content=persona.system_prompt()),
                Message(
                    role=MessageRole.USER,
                    content=(
                        "아래 초안은 토론 발화의 논지입니다. 초안의 사실 범위를 넘지 말고, "
                        "멘토의 말투로 자연스럽게 다듬어 한국어 완성 문장 2~4개로 작성하세요.\n\n"
                        f"토론 주제: {topic}\n"
                        f"이전 발화: {chr(10).join(history) or '없음'}\n"
                        f"초안: {fallback_draft}\n\n"
                        "출력은 발화 본문만 작성하고, 제목이나 목록은 쓰지 마세요."
                    ),
                ),
            ]
            response = await llm.chat(repair_messages, temperature=0.3, max_tokens=700)
            answer = response.text.strip()
    except ExternalServiceError:
        return _fallback_turn(topic, persona, turn_type, context, history)
    if _needs_turn_retry(answer):
        logger.warning(
            "debate.llm_incomplete_answer",
            extra={"topic": topic, "persona_id": persona.id, "turn_type": turn_type},
        )
        return _fallback_turn(topic, persona, turn_type, context, history)
    return answer


async def _generate_debate_script(
    topic: str,
    turns: list[tuple[int, DebatePersona, str, str]],
    context: RAGContext,
) -> dict[int, DebateScriptTurn] | None:
    if not _is_llm_ready():
        return {}

    evidence = _format_evidence(context)
    personas_text = "\n".join(
        f"- turn {turn_index}: {persona.name}({persona.id}) / 관점: {persona.stance}"
        for turn_index, persona, _, _ in turns
    )
    messages = [
        Message(
            role=MessageRole.SYSTEM,
            content=(
                "너는 투자 교육 앱의 토론 진행자이자 작가입니다. "
                "두 투자 멘토가 실제로 대화하듯 자연스럽고 구체적인 한국어 발화를 작성합니다. "
                "뉴스 제목을 기계적으로 붙이지 말고, 뉴스에서 드러나는 핵심 변화를 먼저 이해한 뒤 "
                "각 멘토의 투자 철학으로 해석합니다. 자료 밖 사실은 만들지 않습니다."
            ),
        ),
        Message(
            role=MessageRole.USER,
            content=(
                f"토론 주제: {topic}\n"
                f"검색 키워드: {', '.join(_topic_keywords(topic)) or topic}\n\n"
                f"멘토와 순서:\n{personas_text}\n\n"
                f"참고 컨텍스트:\n{context.as_context_text() or '확인된 참고 자료가 없습니다.'}\n\n"
                f"핵심 뉴스 근거:\n{evidence or '추출된 뉴스 근거가 없습니다.'}\n\n"
                "먼저 뉴스와 컨텍스트를 보고 핵심 논점을 정리한 뒤 3턴 토론을 작성하세요.\n"
                "논점 정리에는 상승 근거, 하락/주의 근거, 아직 불확실한 조건이 모두 들어가야 합니다.\n\n"
                "턴별 논리 규칙:\n"
                "- 1턴은 뉴스의 긍정 근거와 부정/주의 근거를 모두 언급한 뒤, 첫 멘토의 판단 기준으로 무게중심을 제시합니다.\n"
                "- 1턴은 뉴스 하나만으로 결론 내리지 말고, '좋게 볼 부분'과 '아직 확인할 부분'을 함께 둡니다.\n"
                "- 2턴은 반드시 1턴의 핵심 주장 하나를 responds_to에 요약하고, 동의할 부분과 다르게 볼 부분을 함께 제시합니다.\n"
                "- 3턴은 반드시 2턴의 가장 강한 근거 하나를 responds_to에 요약하고, 그 근거를 조건부로 인정하되 투자 판단으로 이어지기 위해 필요한 조건을 counterpoint로 제시합니다.\n"
                "- 각 턴의 content는 claim/responds_to/counterpoint를 자연스러운 대화 문장으로 풀어쓴 결과여야 합니다.\n\n"
                "중요한 문체 규칙:\n"
                "- 사용자가 LLM에게 편하게 물었을 때 돌아오는 답처럼 자연스럽게 말하세요.\n"
                "- 완전히 찬성 또는 완전히 반대하는 식으로 몰지 말고, 긍정/부정 관점을 섞어 균형 있게 답하세요.\n"
                "- 각 멘토는 자기 철학의 무게중심은 유지하되, 상대 관점에서 맞는 부분을 먼저 인정할 수 있습니다.\n"
                "- '최근 기사 ... 보여줍니다' 같은 템플릿 문장은 쓰지 마세요.\n"
                "- 뉴스 제목은 근거가 아니라 검색 단서입니다. 핵심 뉴스 근거의 '핵심:' 문장에 없는 사건 상태를 확정하지 마세요.\n"
                "- 합의, 결렬, 파업, 상장, 실적 발표 같은 사건은 핵심 문장에 직접 있을 때만 사실로 말하세요.\n"
                "- 뉴스 제목은 필요할 때만 따옴표로 짧게 인용하고, 제목을 본문처럼 이어 붙이지 마세요.\n"
                "- 전망치, 목표주가, 퍼센트 수치는 확정 사실처럼 말하지 말고 '일부 전망에서는', '시장이 기대하는 시나리오는'처럼 약하게 표현하세요.\n"
                "- 핵심 뉴스 근거에 '주의:'가 붙은 항목은 주장의 중심 근거로 쓰지 말고 불확실성 또는 확인할 조건으로 다루세요.\n"
                "- 출처가 불명확하거나 과격한 수치는 단독 근거로 삼지 말고 불확실성에 포함하세요.\n"
                "- 각 턴은 3~4개의 완성된 한국어 문장을 한 문단으로 작성하세요.\n"
                "- 한 턴 안에서 줄바꿈을 하지 말고, 2턴도 장황한 설명 대신 핵심 반론만 말하세요.\n"
                "- 목록, 제목, 점수표, 키워드 나열은 금지합니다.\n"
                "- 직접적인 매수/매도 지시는 하지 마세요.\n\n"
                "반드시 JSON만 출력하세요. 형식:\n"
                "{"
                "\"core_issue\":\"...\","
                "\"bullish_evidence\":[\"...\"],"
                "\"bearish_evidence\":[\"...\"],"
                "\"uncertainties\":[\"...\"],"
                "\"turns\":["
                "{\"turn_index\":1,\"claim\":\"...\",\"balanced_view\":\"...\",\"uses_evidence\":[\"...\"],\"content\":\"...\"},"
                "{\"turn_index\":2,\"responds_to\":\"...\",\"agreement\":\"...\",\"counterpoint\":\"...\",\"uses_evidence\":[\"...\"],\"content\":\"...\"},"
                "{\"turn_index\":3,\"responds_to\":\"...\",\"agreement\":\"...\",\"counterpoint\":\"...\",\"uses_evidence\":[\"...\"],\"content\":\"...\"}"
                "]}"
            ),
        ),
    ]
    try:
        response = await llm.chat(messages, temperature=0.55, max_tokens=1600)
    except Exception:
        logger.warning("debate.script_generation_failed", extra={"topic": topic}, exc_info=True)
        return None
    parsed = _parse_debate_script(response.text)
    expected_turns = {turn_index for turn_index, *_ in turns}
    if set(parsed) != expected_turns:
        logger.warning(
            "debate.script_incomplete",
            extra={"topic": topic, "parsed_turns": sorted(parsed), "expected_turns": sorted(expected_turns)},
        )
        return None
    return parsed


def _parse_debate_script(text: str) -> dict[int, DebateScriptTurn]:
    raw = _extract_json_object(text)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("debate.script_parse_failed", extra={"raw": raw[:500]})
        return {}
    turns = payload.get("turns") if isinstance(payload, dict) else None
    if not isinstance(turns, list):
        return {}
    parsed: dict[int, DebateScriptTurn] = {}
    for item in turns:
        if not isinstance(item, dict):
            continue
        try:
            turn_index = int(item.get("turn_index"))
        except (TypeError, ValueError):
            continue
        content = str(item.get("content") or "").strip()
        if content and not _needs_turn_retry(content):
            evidence_values = item.get("uses_evidence") or []
            if not isinstance(evidence_values, list):
                evidence_values = []
            parsed[turn_index] = DebateScriptTurn(
                turn_index=turn_index,
                content=content,
                claim=str(item.get("claim") or "").strip(),
                balanced_view=str(item.get("balanced_view") or "").strip(),
                agreement=str(item.get("agreement") or "").strip(),
                responds_to=str(item.get("responds_to") or "").strip(),
                counterpoint=str(item.get("counterpoint") or "").strip(),
                uses_evidence=tuple(str(value).strip() for value in evidence_values if value),
            )
    return parsed


def _extract_json_object(text: str) -> str:
    raw = text.strip()
    fence_match = re.search(r"```(?:json|JSON)?\s*(.*?)\s*```", raw, re.DOTALL)
    if fence_match:
        raw = fence_match.group(1).strip()

    extracted = _balanced_json_object(raw)
    if extracted:
        return _remove_trailing_json_commas(extracted)
    return raw


def _balanced_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()
    end = text.rfind("}")
    return text[start : end + 1].strip() if end > start else ""


def _remove_trailing_json_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def _build_turn_messages(
    topic: str,
    persona: DebatePersona,
    instruction: str,
    context: RAGContext,
    history: list[str],
) -> list[Message]:
    evidence = _format_evidence(context)
    keywords = ", ".join(_topic_keywords(topic)) or topic
    return [
        Message(role=MessageRole.SYSTEM, content=persona.system_prompt()),
        Message(
            role=MessageRole.USER,
            content=(
                f"토론 주제: {topic}\n\n"
                f"검색 키워드: {keywords}\n\n"
                f"참고 컨텍스트:\n{context.as_context_text() or '확인된 참고 자료가 없습니다.'}\n\n"
                f"핵심 뉴스 근거:\n{evidence or '추출된 뉴스 근거가 없습니다.'}\n\n"
                f"이전 발화:\n{chr(10).join(history) or '없음'}\n\n"
                f"요청: {instruction}\n"
                "토론 방식:\n"
                "- 사용자가 멘토에게 편하게 물어봤을 때 돌아오는 자연스러운 답변처럼 말하세요.\n"
                "- 먼저 뉴스의 핵심 변화를 한 문장으로 소화한 뒤, 당신의 투자 관점으로 그 의미를 해석하세요.\n"
                "- 기사 제목은 검색 단서일 뿐입니다. 핵심 뉴스 근거의 '핵심:' 문장에 없는 사건 상태를 확정하지 마세요.\n"
                "- 기사 제목은 필요할 때만 따옴표로 짧게 언급하고, 제목을 사실 문장처럼 이어 붙이지 마세요.\n"
                "- 자료에 없는 수치나 사건은 만들지 말고, 확인된 뉴스와 컨텍스트에서 드러나는 흐름만 사용하세요.\n"
                "- 핵심 뉴스 근거에 '주의:'가 붙은 전망성 항목은 확정 사실이 아니라 시장 기대 또는 확인할 조건으로만 언급하세요.\n"
                "- 상대 발화가 있으면 상대의 전제를 자연스럽게 받아친 뒤, 당신의 관점으로 다른 해석을 제시하세요.\n"
                "- 직접적인 매수/매도 지시는 피하되, 지금 판단에서 무엇을 더 확인해야 하는지는 구체적으로 남겨 주세요.\n\n"
                "출력 규칙:\n"
                "- 한국어 자연문 3~5문장으로 작성하세요.\n"
                "- 각 문장은 완결된 서술어로 끝내세요.\n"
                "- '최근 기사 ... 보여줍니다' 같은 템플릿 문장을 반복하지 마세요.\n"
                "- 제목, 명사구, 키워드, 목록, 한 문장 이하의 짧은 요약은 금지합니다.\n"
                "- 멘토의 관점은 살리되, 보고서체나 정형화된 목록처럼 쓰지 마세요."
            ),
        ),
    ]


def _needs_turn_retry(answer: str) -> bool:
    compact = " ".join(answer.split())
    if len(compact) < 45:
        return True
    sentence_count = len(
        re.findall(r"(?:[.!?。]|다(?=\s|$)|요(?=\s|$)|니다(?=\s|$)|습니다(?=\s|$))", compact)
    )
    if sentence_count < 2:
        return True
    return not compact.endswith((".", "!", "?", "다", "요", "니다", "습니다"))


def _is_llm_ready() -> bool:
    return llm.configured


async def _check_answer(
    answer: str,
    persona: DebatePersona,
    context: RAGContext,
) -> tuple[str, CriticResult | None]:
    output_check = guardrail.check_output(answer)
    if not output_check.ok:
        raise BadRequestError(output_check.reason)
    if not _is_llm_ready():
        return answer, None
    try:
        verified = await hallucination.verify(answer, context)
    except ExternalServiceError:
        return answer, None
    if not verified:
        answer = "확인된 정보가 없습니다. 제공된 근거 안에서만 토론을 이어가겠습니다."
    try:
        critic_result = await critic.evaluate(answer, persona.id, context)
    except ExternalServiceError:
        return answer, None
    if not critic_result.ok:
        raise BadRequestError(critic_result.reason)
    return answer, critic_result


def _fallback_turn(
    topic: str,
    persona: DebatePersona,
    turn_type: str,
    context: RAGContext,
    history: list[str],
) -> str:
    evidence = _extract_news_evidence(context)
    previous = history[-1] if history else ""
    if turn_type == "opinion":
        return _fallback_opening(topic, persona, evidence)
    if turn_type == "rebuttal":
        return _fallback_rebuttal(topic, persona, evidence, previous)
    return _fallback_counter(topic, persona, evidence, previous)


def _fallback_opening(
    topic: str,
    persona: DebatePersona,
    evidence: list[NewsEvidence],
) -> str:
    lead = evidence[0] if evidence else None
    if not lead:
        return (
            f"{topic}에 대해 확인된 참고 자료가 부족합니다. "
            "지금은 결론을 앞세우기보다 핵심 지표와 반대 근거를 더 확인해야 합니다."
        )
    news_point = _natural_news_reference(lead)
    if persona.id in {"value", "dividend"}:
        return (
            f"{news_point} 이건 불확실성이 줄었다는 점에서는 분명 긍정적입니다. "
            f"다만 저는 {_topic_object(topic)} 단기 호재로만 보기보다, "
            "그 변화가 실제 현금흐름과 주주환원 여력으로 이어지는지 함께 확인하겠습니다. "
            "가격에 이미 기대가 많이 반영돼 있다면 좋은 뉴스가 나와도 안전마진은 얇아질 수 있습니다."
        )
    return (
        f"{news_point} 성장 관점에서는 이런 변화가 실적 추정과 시장의 관심을 동시에 움직일 수 있다는 점이 긍정적입니다. "
        "다만 기대감만 앞서는지, 실제 매출 성장과 수급 개선이 뒤따르는지는 분리해서 봐야 합니다."
    )


def _fallback_rebuttal(
    topic: str,
    persona: DebatePersona,
    evidence: list[NewsEvidence],
    previous: str,
) -> str:
    lead = (evidence[1:] or evidence or [None])[0]
    news_point = _natural_news_reference(lead) if lead else "반대 근거도 아직은 제한적입니다."
    previous_point = _previous_point(previous)
    if persona.id in {"momentum", "growth"}:
        return (
            f"{previous_point} 그 점에는 동의하지만, 그 기준만으로 결론을 미루면 변화의 속도를 놓칠 수 있습니다. "
            f"{news_point} 제가 다르게 보는 지점은 리스크가 있다는 사실 자체가 아니라, "
            "그 리스크보다 실적 추정과 수급이 더 빠르게 개선되는지입니다."
        )
    return (
        f"{previous_point} "
        f"다만 {news_point} 성장 논리 자체는 이해하지만, 좋은 산업이라는 말이 곧 좋은 매수가격을 뜻하지는 않습니다. "
        f"{topic}도 기대가 가격에 얼마나 반영됐는지와 현금흐름으로 확인되는지를 분리해서 봐야 합니다."
    )


def _fallback_counter(
    topic: str,
    persona: DebatePersona,
    evidence: list[NewsEvidence],
    previous: str,
) -> str:
    lead = (evidence[-1:] or evidence or [None])[0]
    news_point = _natural_news_reference(lead) if lead else "아직 확인할 지표가 남아 있습니다."
    previous_point = _previous_point(previous)
    if persona.id in {"value", "dividend"}:
        return (
            f"{previous_point} 저도 그 가능성은 인정합니다. 다만 성장 전망이 강하다는 말과 지금 가격이 합리적이라는 말은 다릅니다. "
            f"{news_point} 저는 여기서 그 기대가 이미 주가에 얼마나 반영됐는지, "
            "그리고 다음 실적에서 실제 잉여현금흐름으로 바뀌는지를 확인하겠습니다."
        )
    return (
        f"{previous_point} "
        f"그 우려는 필요하지만, {news_point} 보수적인 가격 기준만으로는 업황 전환 초입을 놓칠 수 있습니다. "
        f"실적 추정이 계속 올라가고 자본비용을 넘는 성장이 확인된다면 {topic}에 일부 프리미엄을 주는 판단도 가능합니다."
    )


@dataclass(frozen=True)
class NewsEvidence:
    title: str
    source: str
    url: str
    sentence: str

    def as_text(self) -> str:
        label = self.title or self.source
        if not label:
            return self.sentence
        source = f" ({self.source})" if self.source and self.source != label else ""
        return f"최근 기사 \"{label}\"{source}는 {self.fact_clause()}을 보여줍니다"

    def fact_clause(self) -> str:
        return _to_fact_clause(self.sentence)

    @property
    def is_speculative(self) -> bool:
        return _is_speculative_news(self.title) or _is_speculative_news(self.sentence)

    def caution_note(self) -> str:
        if not self.is_speculative:
            return ""
        return "전망성 기사이므로 확정 사실이 아니라 시장 기대 또는 시나리오로만 다뤄야 함"

    def as_prompt_line(self) -> str:
        url = f" {self.url}" if self.url else ""
        title = self.title or self.source or "뉴스"
        source = f" / 출처: {self.source}" if self.source else ""
        caution = f" / 주의: {self.caution_note()}" if self.caution_note() else ""
        return f"제목: \"{title}\"{source} / 핵심: {self.fact_clause()}{caution}{url}"


def _extract_news_evidence(context: RAGContext, limit: int = 3) -> list[NewsEvidence]:
    points: list[NewsEvidence] = []
    for doc in context.documents:
        title = str(doc.metadata.get("title") or doc.metadata.get("headline") or "").strip()
        source = str(doc.metadata.get("source") or "").strip()
        url = str(doc.metadata.get("url") or "").strip()
        if _is_low_signal_news(title, source, url):
            continue
        sentence = _extract_news_summary(doc.text, title)
        if not sentence:
            continue
        points.append(NewsEvidence(title=title, source=source, url=url, sentence=sentence))
        if len(points) >= limit:
            break
    return points


def _format_evidence(context: RAGContext) -> str:
    return "\n".join(f"- {point.as_prompt_line()}" for point in _extract_news_evidence(context))


def _is_low_signal_news(title: str, source: str, url: str) -> bool:
    haystack = " ".join([title, source, url])
    if "fathomjournal.org" in haystack.lower():
        return True
    if re.search(r"\([A-Za-z0-9]{8,}\)", title):
        return True
    return False


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


def _extract_news_summary(text: str, title: str, max_chars: int = 130) -> str:
    compact = " ".join(text.split())
    title = " ".join(title.split())
    if title and compact.startswith(title):
        compact = compact[len(title) :].lstrip(" .-–—:|")
    sentences = _split_sentences(compact)
    for sentence in sentences:
        clean = _clean_news_sentence(sentence, title)
        if clean and not _looks_like_title(clean, title):
            return clean[:max_chars].rstrip(" .!?。")
    if compact:
        clean = _clean_news_sentence(compact[:max_chars], title).rstrip(" .!?。")
        if clean and not _looks_like_title(clean, title):
            return clean
    return _summarize_news_title(title)[:max_chars].rstrip(" .!?。")


def _split_sentences(text: str) -> list[str]:
    compact = " ".join(text.split())
    if not compact:
        return []
    parts = re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+", compact)
    return [part.strip() for part in parts if part.strip()]


def _clean_news_sentence(sentence: str, title: str) -> str:
    clean = re.sub(r"<[^>]+>", "", sentence)
    clean = re.sub(r"\s+-\s+[^-]{2,40}$", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" .!?。")
    if title and clean.startswith(title):
        clean = clean[len(title) :].lstrip(" .-–—:|")
    return clean


def _looks_like_title(sentence: str, title: str) -> bool:
    if not sentence:
        return True
    if title and sentence == title:
        return True
    if not re.search(r"(다|요|니다|습니다|했다|있다|없다|된다|이다)$", sentence):
        return True
    if re.search(r"\b[a-z0-9-]+\.(com|net|org|kr|co\.kr)\b", sentence, re.IGNORECASE):
        return True
    if re.search(r"(사야\s*(할까|하나)|팔아야|살까요|팔까요|어떻게|왜|\?)", sentence):
        return True
    return len(sentence) < 12 or sentence.count(" ") < 2


def _summarize_news_title(title: str) -> str:
    clean = re.sub(r"^\[[^\]]+\]\s*", "", title)
    clean = re.sub(r"\s+-\s+[^-]{2,40}$", "", clean)
    clean = re.sub(r"\([^)]{2,40}\)", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" .!?。")
    if re.search(r"\bAI\b|인공지능", clean, re.IGNORECASE):
        if re.search(r"거품|버블|조정|폭락|급락|대비", clean):
            return "AI 관련 주식의 가격 상승 기대와 조정 우려가 함께 부각되고 있다"
        if re.search(r"폭등|급등|상승|랠리", clean):
            return "AI 관련 주식의 상승세가 이어지며 기대와 가격 부담이 함께 커지고 있다"
        return "AI 투자 열기가 시장별로 다르게 반영되며 기회와 과열 논쟁이 함께 나타나고 있다"
    if re.search(r"삼성전자|하이닉스|SK하이닉스", clean):
        if re.search(r"사야|살까요|매수", clean):
            return "삼성전자와 반도체주의 매수 타이밍이 투자자들의 핵심 쟁점으로 다뤄지고 있다"
        if re.search(r"DRAM|HBM|메모리|반도체", clean, re.IGNORECASE):
            return "메모리 업황 변화가 삼성전자 실적 기대와 투자 판단에 영향을 주고 있다"
    if re.search(r"폭등|급등|상승|돌파", clean):
        return "가격 상승 이후 기대와 부담을 함께 따져야 하는 국면이 부각되고 있다"
    if re.search(r"폭락|급락|하락|흔들", clean):
        return "주가 변동성이 커진 상황에서 매도와 추가 매수 판단이 엇갈리고 있다"
    if re.search(r"실적|전망|목표주가", clean):
        return "실적 전망과 목표주가 변화가 투자 판단의 주요 변수로 다뤄지고 있다"
    return f"{clean} 이슈가 투자 판단의 변수로 다뤄지고 있다" if clean else "관련 뉴스가 투자 판단의 변수로 다뤄지고 있다"


def _to_fact_clause(sentence: str) -> str:
    clean = sentence.strip(" .!?。")
    if clean.endswith("이다"):
        return f"{clean[:-2]}이라는 점"
    if clean.endswith("있다"):
        return f"{clean[:-2]}있다는 점"
    if clean.endswith("없다"):
        return f"{clean[:-2]}없다는 점"
    if clean.endswith("했다"):
        return f"{clean[:-2]}했다는 점"
    if clean.endswith("된다"):
        return f"{clean[:-2]}된다는 점"
    if clean.endswith("다"):
        return f"{clean[:-1]}다는 점"
    return f"{clean}라는 점"


def _natural_news_reference(evidence: NewsEvidence) -> str:
    title = evidence.title or evidence.source or "관련 뉴스"
    quoted = f"\"{title}\""
    fact = evidence.fact_clause()
    caution = " 다만 이건 전망성 기사라 확정 사실처럼 받아들이면 안 됩니다." if evidence.is_speculative else ""
    if evidence.source:
        return f"{quoted}({evidence.source})을 보면 {fact}입니다.{caution}"
    return f"{quoted}을 보면 {fact}입니다.{caution}"


def _is_speculative_news(text: str) -> bool:
    if not text:
        return False
    return bool(
        re.search(
            r"(목표가|목표주가|전망|간다|급등|폭등|턱밑|[0-9]+만원|[0-9]+%|[0-9]+조)",
            text,
            re.IGNORECASE,
        )
    )


def _topic_object(topic: str) -> str:
    return f"{topic}{_object_particle(topic)}"


def _object_particle(text: str) -> str:
    last = text.strip()[-1:] if text.strip() else ""
    if not last:
        return "을"
    code = ord(last)
    if 0xAC00 <= code <= 0xD7A3:
        return "을" if (code - 0xAC00) % 28 else "를"
    return "을"


def _previous_point(previous: str, max_chars: int = 42) -> str:
    text = previous.split(":", maxsplit=1)[-1].strip()
    if previous.startswith(("모멘텀 멘토", "성장주 멘토")):
        return "변화 속도와 실적 추격을 보자는 반론은 일리가 있습니다."
    if previous.startswith(("가치투자 멘토", "배당주 멘토")):
        return "현금흐름과 안전마진을 먼저 확인하자는 말은 타당합니다."
    if "현금흐름" in text or "안전마진" in text:
        return "현금흐름과 안전마진을 먼저 확인하자는 말은 타당합니다."
    if "변화의 속도" in text or "기대를 따라잡는 속도" in text or "실적" in text:
        return "변화 속도와 실적 추격을 보자는 반론은 일리가 있습니다."
    if "성장 초입" in text or "점유율" in text:
        return "성장 초입을 놓칠 수 있다는 반론은 이해합니다."
    if "매수가격" in text or "좋은 산업" in text:
        return "좋은 산업과 좋은 가격을 구분하자는 기준은 필요합니다."
    if not text:
        return "앞선 주장은 검토할 가치가 있습니다."
    return f"{text[:max_chars].rstrip(' .')}라는 취지는 이해합니다."


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
