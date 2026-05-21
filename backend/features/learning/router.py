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
from core.user_context import user_context

from . import curriculum, service
from .schemas import (
    ChatStreamReq,
    CreateSessionReq,
    MessageListRes,
    MessageRes,
    QuizOption,
    QuizRes,
    SendMessageReq,
    SessionListRes,
    SessionRes,
    SubmitQuizReq,
    SubmitQuizRes,
    TierQuizCatalogRes,
)

router = APIRouter(prefix="/api/learning", tags=["learning"])


def _to_quiz_response(item: curriculum.QuizItem) -> QuizRes:
    return QuizRes(
        concept_id=item.concept_id,
        concept_name=item.concept_name,
        question=item.question,
        options=[QuizOption(index=idx, text=opt_text) for idx, opt_text in enumerate(item.options)],
    )


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


@router.get("/me/quizzes", response_model=TierQuizCatalogRes)
async def list_current_tier_quizzes(
    user: User = Depends(get_current_user),
) -> TierQuizCatalogRes:
    """현재 티어에서 풀 수 있는 개념 퀴즈 목록."""
    current_tier = await user_context.get_tier(UserId(user.id))
    quizzes = curriculum.list_quizzes_for_tier(current_tier)
    return TierQuizCatalogRes(
        tier=current_tier.value,
        quizzes=[_to_quiz_response(item) for item in quizzes],
    )


@router.get("/quizzes/{concept_id}", response_model=QuizRes)
async def get_quiz(
    concept_id: int,
    user: User = Depends(get_current_user),
) -> QuizRes:
    """투자 개념 확인 퀴즈 조회."""
    item = curriculum.get_quiz(concept_id)
    return _to_quiz_response(item)


@router.post("/quizzes/submit", response_model=SubmitQuizRes)
async def submit_quiz(
    req: SubmitQuizReq,
    user: User = Depends(get_current_user),
) -> SubmitQuizRes:
    """퀴즈 정답 제출 및 채점. 정답 시 ConceptMasteredEvent 발행."""
    is_correct, explanation = curriculum.grade_quiz(req.concept_id, req.answer_index)

    if is_correct:
        await event_bus.publish(
            ConceptMasteredEvent(
                user_id=UserId(user.id),
                concept_id=ConceptId(req.concept_id),
            )
        )

    return SubmitQuizRes(correct=is_correct, explanation=explanation)
