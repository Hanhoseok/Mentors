"""학습 동 서비스 — 세션·메시지 CRUD 및 멘토 채팅 스트리밍.

owner: learning
관련 FR: FR-02, UC-04, UC-10
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai_pipeline import critic, guardrail, hallucination, rag, tier_overlay
from core.contracts import MentorId, MessageRole, MessageSentEvent, SessionId, UserId
from core.db import SessionLocal
from core.event_bus import event_bus
from core.exceptions import NotFoundError
from core.llm import Message, llm
from core.read_services import DailyReportRef, daily_report_reader
from core.user_context import user_context

from .models import ChatMessage, ChatSession, DailyOpenerLog
from .personas import get_mentor_strategy, get_opener, get_system_prompt
from .quizzes import recommend_tier_quiz_for_chat, serialize_tier_quiz

logger = logging.getLogger("learning.service")


async def create_session(
    user_id: UserId,
    mentor_id: MentorId,
    db: AsyncSession,
) -> ChatSession:
    """새 멘토 채팅 세션 생성."""
    session = ChatSession(user_id=user_id, mentor_id=mentor_id)
    db.add(session)
    await db.flush()
    logger.info(
        "learning.session_created",
        extra={"user_id": user_id, "session_id": session.id, "mentor_id": mentor_id},
    )
    return session


async def list_sessions(user_id: UserId, db: AsyncSession) -> list[ChatSession]:
    """사용자의 채팅 세션 목록 (최신순)."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_session(
    session_id: SessionId,
    user_id: UserId,
    db: AsyncSession,
) -> ChatSession:
    """세션 조회 (본인 소유 확인)."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        raise NotFoundError("채팅 세션을 찾을 수 없습니다")
    return session


async def list_messages(
    session_id: SessionId,
    user_id: UserId,
    db: AsyncSession,
) -> list[ChatMessage]:
    """세션의 메시지 목록 (시간순)."""
    await get_session(session_id, user_id, db)

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def add_message(
    session_id: SessionId,
    user_id: UserId,
    role: str,
    content: str,
    db: AsyncSession,
) -> ChatMessage:
    """메시지 저장 + 세션 제목 자동 생성 + 이벤트 발행."""
    session = await get_session(session_id, user_id, db)

    message = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(message)

    # 첫 사용자 메시지면 세션 제목 자동 설정 (최대 50자)
    if role == "user" and session.title is None:
        session.title = content[:50]

    await db.flush()

    # 사용자 메시지일 때만 이벤트 발행
    if role == "user":
        await event_bus.publish(
            MessageSentEvent(
                user_id=user_id,
                session_id=SessionId(session_id),
                mentor_id=MentorId(session.mentor_id),
            )
        )

    logger.info(
        "learning.message_added",
        extra={"user_id": user_id, "session_id": session_id, "role": role},
    )
    return message


async def get_today_opener(
    user_id: UserId,
    mentor_id: MentorId,
    db: AsyncSession,
) -> tuple[bool, str, DailyReportRef]:
    """그날 그 멘토 첫 진입: 오늘 리포트 get-or-create + 1일 1회 dedup 마커.

    멘토 id로 전략을 풀고(동 내부 매핑), daily_report_reader로 오늘 리포트를
    get-or-create 한 뒤 (user, mentor, 리포트 날짜) 마커를 멱등 upsert 한다.
    ON CONFLICT DO NOTHING + RETURNING으로 '이번 호출이 첫 진입인지'를 판정해
    카드 노출 여부(first_today)를 정한다. 마커 날짜는 리포트 날짜에 맞춰
    daily_report 동의 KST '오늘' 정의와 어긋나지 않게 한다.

    커밋은 호출하는 라우터가 담당한다(동 관례).
    """
    strategy = get_mentor_strategy(mentor_id)
    report = await daily_report_reader.get_or_create_today_report(user_id, strategy)

    inserted_id = await db.scalar(
        pg_insert(DailyOpenerLog)
        .values(
            user_id=int(user_id),
            mentor_id=int(mentor_id),
            opened_date=report.report_date,
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "mentor_id", "opened_date"]
        )
        .returning(DailyOpenerLog.id)
    )
    first_today = inserted_id is not None

    logger.info(
        "learning.today_opener",
        extra={
            "user_id": user_id,
            "mentor_id": mentor_id,
            "report_id": report.id,
            "first_today": first_today,
        },
    )
    return first_today, get_opener(strategy), report


async def stream_assistant_response(
    session_id: SessionId,
    user_id: UserId,
    user_content: str,
) -> AsyncIterator[dict[str, Any]]:
    """멘토의 SSE 스트리밍 응답을 생성하고 완료 후 DB에 저장한다.

    - 별도의 SessionLocal을 사용하여 SSE 연결 중/종료 후에도 안전하게 DB 트랜잭션 관리.
    - AI 파이프라인 적용: RAG 검색 → 티어 오버레이 → 스트리밍 → 환각/critic 검증.
    """
    # 1. 컨텍스트 및 DB 세션 로드
    user_ctx = await user_context.get_for_mentor_chat(user_id)

    async with SessionLocal() as db:
        session = await get_session(session_id, user_id, db)
        history = await list_messages(session_id, user_id, db)

        # 2. 시스템 프롬프트 및 RAG 지식 준비
        strategy = get_mentor_strategy(session.mentor_id)
        base_prompt = get_system_prompt(strategy)
        system_prompt = tier_overlay.apply(base_prompt, user_ctx.tier)

        rag_ctx = await rag.retrieve(query=user_content, collection="learning_kb")
        if not rag_ctx.is_empty:
            system_prompt += (
                "\n\n[참고 지식 - 출처 표기 준수]\n"
                "다음 참고 지식을 바탕으로 답변하고, 참고한 부분에는 반드시 "
                "'[출처: doc_id]' 형태로 출처를 표기해라.\n\n"
                f"{rag_ctx.as_context_text()}"
            )

        # 3. LLM 메시지 구성
        llm_messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        for msg in history:
            llm_messages.append(Message(role=MessageRole(msg.role), content=msg.content))

        # 4. 스트리밍 응답 생성 — 멘토 답변은 길어질 수 있으므로 기본 1000을 상향.
        # core.llm 기본값은 짧은 요약 워크로드에 맞춰져 있어 학습 동에선 명시적으로 늘림.
        full_answer = ""
        async for chunk in llm.chat_stream(messages=llm_messages, max_tokens=4096):
            if chunk.delta:
                full_answer += chunk.delta
            yield {"event": "delta", "data": chunk.model_dump_json()}

        # 5. 후처리 검증 (환각, 페르소나 이탈, 출력 가드레일)
        is_valid = await hallucination.verify(full_answer, rag_ctx)
        if not is_valid:
            logger.warning("learning.hallucination_detected", extra={"session_id": session_id})

        c_res = await critic.evaluate(full_answer, strategy.value, rag_ctx)
        if not c_res.ok:
            logger.warning(
                "learning.critic_warning",
                extra={"session_id": session_id, "reason": c_res.reason},
            )

        g_out = guardrail.check_output(full_answer)
        if not g_out.ok:
            logger.warning(
                "learning.output_guardrail_failed",
                extra={"session_id": session_id, "reason": g_out.reason},
            )

        recommended_quiz = await recommend_tier_quiz_for_chat(
            user_id=user_id,
            tier=user_ctx.tier,
            text=f"{user_content}\n{full_answer}",
            db=db,
        )

        # 6. 최종 응답 DB 저장
        assistant_msg = ChatMessage(session_id=session_id, role="assistant", content=full_answer)
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=full_answer,
        )
        db.add(assistant_msg)
        await db.commit()

        logger.info(
            "learning.assistant_response_saved",
            extra={"session_id": session_id, "length": len(full_answer)},
        )

        if recommended_quiz is not None:
            yield {
                "event": "follow_up_quiz",
                "data": json.dumps(
                    serialize_tier_quiz(recommended_quiz),
                    ensure_ascii=False,
                ),
            }
