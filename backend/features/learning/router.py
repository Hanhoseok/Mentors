"""2동 — 학습 (멘토 채팅·개념퀴즈·기록).

owner: learning
관련 FR: FR-02, UC-04, UC-10
핵심 의존성: core/ai_pipeline (RAG·Guardrail·Hallucination·Critic·TierOverlay)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from core.ai_pipeline import guardrail
from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.contracts import ConceptId, ConceptMasteredEvent, MentorId, SessionId, UserId
from core.db import get_db
from core.event_bus import event_bus
from core.exceptions import BadRequestError

from . import curriculum, quizzes, service
from .schemas import (
    ChatStreamReq,
    CreateSessionReq,
    CurrentTierQuizzesRes,
    DailyReportCard,
    MessageListRes,
    MessageRes,
    QuizOption,
    QuizRes,
    SendMessageReq,
    SessionListRes,
    SessionRes,
    SubmitQuizReq,
    SubmitQuizRes,
    TierQuizItemRes,
    TodayOpenerRes,
)

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/sessions", response_model=SessionListRes)
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionListRes:
    """사용자의 멘토 채팅 세션 목록 (최신순)."""
    sessions = await service.list_sessions(UserId(user.id), db)
    return SessionListRes(sessions=[SessionRes.model_validate(s) for s in sessions])


@router.post("/sessions", response_model=SessionRes)
async def create_session(
    req: CreateSessionReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionRes:
    """새 멘토 채팅 세션 생성."""
    session = await service.create_session(
        user_id=UserId(user.id),
        mentor_id=MentorId(req.mentor_id),
        db=db,
    )
    await db.commit()
    return SessionRes.model_validate(session)


@router.get("/sessions/{session_id}/messages", response_model=MessageListRes)
async def list_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageListRes:
    """세션의 메시지 목록 (시간순)."""
    messages = await service.list_messages(
        session_id=SessionId(session_id),
        user_id=UserId(user.id),
        db=db,
    )
    return MessageListRes(messages=[MessageRes.model_validate(m) for m in messages])


@router.post("/sessions/{session_id}/messages", response_model=MessageRes)
async def send_message(
    session_id: int,
    req: SendMessageReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageRes:
    """메시지 전송 (단순 저장용). 실제 멘토 대화는 /chat/stream 사용을 권장."""
    message = await service.add_message(
        session_id=SessionId(session_id),
        user_id=UserId(user.id),
        role="user",
        content=req.content,
        db=db,
    )
    await db.commit()
    return MessageRes.model_validate(message)


@router.post("/chat/stream")
async def chat_stream(
    req: ChatStreamReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """멘토와의 실시간 채팅 스트리밍 엔드포인트 (SSE).

    - 입력 가드레일 확인 후 사용자 메시지 저장.
    - AI 파이프라인(RAG → 티어 오버레이 → 스트리밍 → 후처리 검증)을 거쳐 응답 반환.
    """
    g = guardrail.check_input(req.content)
    if not g.ok:
        raise BadRequestError(g.reason or "입력 가드레일 차단")

    await service.add_message(
        session_id=SessionId(req.session_id),
        user_id=UserId(user.id),
        role="user",
        content=req.content,
        db=db,
    )
    await db.commit()

    return EventSourceResponse(
        service.stream_assistant_response(
            session_id=SessionId(req.session_id),
            user_id=UserId(user.id),
            user_content=req.content,
        )
    )


@router.get("/mentors/{mentor_id}/today-opener", response_model=TodayOpenerRes)
async def today_opener(
    mentor_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TodayOpenerRes:
    """그날 그 멘토 첫 진입 — 오늘 리포트를 get-or-create 하고 1일 1회 카드 노출 마커를 찍는다.

    first_today=True면 프론트가 일일 리포트 카드를 노출(하루 한 번). 재진입이면
    first_today=False지만 report는 동일하게 내려 '전체 리포트 보기' 딥링크는 유지.
    """
    first_today, opener, report = await service.get_today_opener(
        UserId(user.id), MentorId(mentor_id), db
    )
    await db.commit()
    return TodayOpenerRes(
        first_today=first_today,
        opener=opener,
        report=DailyReportCard(
            id=report.id,
            report_date=report.report_date,
            mentor_strategy=report.mentor_strategy.value,
            tier=report.tier.value,
            status=report.status,
            body=report.body,
            highlights=report.highlights,
        ),
    )


@router.get("/quizzes/{concept_id}", response_model=QuizRes)
async def get_quiz(
    concept_id: int,
    user: User = Depends(get_current_user),
) -> QuizRes:
    """투자 개념 확인 퀴즈 조회."""
    item = curriculum.get_quiz(concept_id)
    options = [QuizOption(index=idx, text=opt_text) for idx, opt_text in enumerate(item.options)]
    return QuizRes(
        concept_id=item.concept_id,
        concept_name=item.concept_name,
        question=item.question,
        options=options,
    )


@router.get("/me/quizzes", response_model=CurrentTierQuizzesRes)
async def get_current_tier_quizzes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentTierQuizzesRes:
    tier, quiz_states = await quizzes.list_current_tier_quizzes(UserId(user.id), db)
    return CurrentTierQuizzesRes(
        tier=tier.value,
        quizzes=[
            TierQuizItemRes.model_validate(quizzes.serialize_tier_quiz_state(state))
            for state in quiz_states
        ],
    )


@router.post("/quizzes/submit", response_model=SubmitQuizRes)
async def submit_quiz(
    req: SubmitQuizReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmitQuizRes:
    """퀴즈 정답 제출 및 채점. 정답 시 ConceptMasteredEvent 발행."""
    user_id = UserId(user.id)
    if req.question_id is not None or (req.concept_id is not None and req.concept_id >= 100):
        question_id = quizzes.resolve_question_id(
            question_id=req.question_id,
            concept_id=req.concept_id,
            quiz_index=req.quiz_index,
        )
        outcome = await quizzes.submit_tier_quiz(
            user_id=user_id,
            question_id=question_id,
            answer_index=req.answer_index,
            db=db,
        )
        await db.commit()

        if outcome.correct:
            await event_bus.publish(
                ConceptMasteredEvent(
                    user_id=user_id,
                    concept_id=ConceptId(outcome.quiz.concept_id),
                )
            )

        return SubmitQuizRes(correct=outcome.correct, explanation=outcome.explanation)

    assert req.concept_id is not None
    is_correct, explanation = curriculum.grade_quiz(req.concept_id, req.answer_index)
    if is_correct:
        await event_bus.publish(
            ConceptMasteredEvent(
                user_id=user_id,
                concept_id=ConceptId(req.concept_id),
            )
        )

    return SubmitQuizRes(correct=is_correct, explanation=explanation)
