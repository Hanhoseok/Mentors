"""4동 — 토론 (투기장).

owner: TODO
관련 FR: FR-04, UC-03
**중요**: ADR-011 — core/ai_pipeline의 빌딩블록 직접 사용. features/learning import 금지.
페르소나는 토론 동 자체 정의 또는 core/contracts에 공용 등재.
"""

from fastapi import APIRouter, Depends

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.contracts import Tier, UserId
from core.exceptions import ForbiddenError
from core.user_context import user_context

router = APIRouter(prefix="/api/debate", tags=["debate"])


@router.get("/eligibility")
async def eligibility(user: User = Depends(get_current_user)) -> dict[str, bool | str]:
    # BR-01: 투기장 기능은 T2 이상 사용자에게만 활성화된다
    tier = await user_context.get_tier(UserId(user.id))
    if tier == Tier.T1:
        raise ForbiddenError("투기장은 T2부터 활성화됩니다 (BR-01)")
    return {"allowed": True, "tier": tier.value}
