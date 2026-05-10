"""3동 — 성장 (티어·승급시험·이해도 게이지).

owner: TODO
관련 FR: FR-07, FR-10, UC-07
이벤트: PromotionEligibleEvent (FCM 푸시 트리거), PromotionTestPassedEvent
"""

from fastapi import APIRouter, Depends

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.contracts import Tier, UserId
from core.user_context import user_context

router = APIRouter(prefix="/api/growth", tags=["growth"])


@router.get("/me/tier")
async def my_tier(user: User = Depends(get_current_user)) -> dict[str, str]:
    tier: Tier = await user_context.get_tier(UserId(user.id))
    return {"tier": tier.value, "next": tier.next.value if tier.next else "max"}
