"""1동 — 온보딩 (성향 분석·멘토 추천·T1 배정).

owner: TODO
관련 FR: FR-01, UC-01
"""

from fastapi import APIRouter, Depends

from core.auth.dependencies import get_current_user
from core.auth.models import User

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/status")
async def status(user: User = Depends(get_current_user)) -> dict[str, str | bool]:
    # TODO: 실제 온보딩 완료 여부 확인 로직 (user_profiles 테이블 등)
    return {"user_id": str(user.id), "onboarded": False}
