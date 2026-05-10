"""2동 — 학습 (멘토 채팅·개념퀴즈·기록).

owner: TODO
관련 FR: FR-02, UC-04, UC-10
핵심 의존성: core/ai_pipeline (RAG·Guardrail·Hallucination·Critic·TierOverlay)
"""

from fastapi import APIRouter, Depends

from core.auth.dependencies import get_current_user
from core.auth.models import User

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user)) -> dict[str, list[str]]:
    # TODO: 멘토 채팅 세션 조회
    return {"sessions": []}
