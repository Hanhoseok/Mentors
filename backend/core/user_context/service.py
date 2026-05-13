"""UserContextService — 사용자 상태 단일 read 창구 (§4.6, ADR-003).

Day 6 MVP:
- User 테이블(코어)에서 nickname/status 조회
- tier/interests/mentor 등 동 자체 데이터는 디폴트 (각 동 owner가 PR로 확장)

향후 확장 패턴:
- 성장 동의 GrowthReader가 등록되면 get_tier()를 위임
- 온보딩 동이 user_profiles 추가하면 get_interests() 위임
"""

import logging
from datetime import datetime

from core.auth.models import User
from core.cache import make_cache
from core.contracts import (
    MentorId,
    Tier,
    UserId,
    UserStatus,
    UserUpdatedEvent,
)
from core.db import SessionLocal
from core.event_bus import event_bus
from core.exceptions import NotFoundError

from .dto import (
    DailyReportContext,
    DebateContext,
    MentorChatContext,
    PromotionTestContext,
    UserContextBase,
)

logger = logging.getLogger("user_context")
_CACHE_TTL = 300  # 5분 (§7.3)


class UserContextService:
    def __init__(self) -> None:
        self._cache = make_cache("user_context")

    # --- 단일 값 getter ---

    async def get_tier(self, user_id: UserId) -> Tier:
        # TODO: 성장 동 owner가 GrowthReader 등록 시 위임
        return Tier.T1

    async def get_interests(self, user_id: UserId) -> list[str]:
        # TODO: 온보딩 동이 user_profiles 추가하면 위임
        return []

    async def get_status(self, user_id: UserId) -> UserStatus:
        user = await self._load_user(user_id)
        return UserStatus(user.status)

    # --- Use-case DTO ---

    async def get_for_mentor_chat(self, user_id: UserId) -> MentorChatContext:
        base = await self._load_base(user_id)
        return MentorChatContext(
            **base.model_dump(),
            interests=await self.get_interests(user_id),
            selected_mentor_id=await self._get_selected_mentor(user_id),
        )

    async def get_for_daily_report(self, user_id: UserId) -> DailyReportContext:
        base = await self._load_base(user_id)
        return DailyReportContext(
            **base.model_dump(),
            today_chat_count=0,  # TODO: 학습 동 위임
            today_scrap_count=0,  # TODO: 콘텐츠 동 위임
        )

    async def get_for_promotion_test(self, user_id: UserId) -> PromotionTestContext:
        base = await self._load_base(user_id)
        return PromotionTestContext(
            **base.model_dump(),
            chat_count_this_week=0,  # TODO: 학습 동 위임
            last_promotion_attempt_at=None,  # TODO: 성장 동 위임
        )

    async def get_for_debate(self, user_id: UserId) -> DebateContext:
        base = await self._load_base(user_id)
        return DebateContext(
            **base.model_dump(),
            interests=await self.get_interests(user_id),
        )

    # --- 캐시 무효화 (이벤트 구독) ---

    async def invalidate(self, user_id: UserId) -> None:
        await self._cache.delete(f"base:{user_id}")
        await self._cache.delete(f"tier:{user_id}")
        await self._cache.delete(f"interests:{user_id}")

    # --- 내부 ---

    async def _load_base(self, user_id: UserId) -> UserContextBase:
        user = await self._load_user(user_id)
        return UserContextBase(
            user_id=user_id,
            nickname=user.nickname,
            tier=await self.get_tier(user_id),
            status=UserStatus(user.status),
        )

    async def _load_user(self, user_id: UserId) -> User:
        async with SessionLocal() as session:
            user = await session.get(User, user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def _get_selected_mentor(self, user_id: UserId) -> MentorId | None:
        # TODO: 학습 동 위임
        return None


user_context = UserContextService()


# --- 이벤트 구독 (UserUpdatedEvent 시 캐시 무효화) ---


async def _on_user_updated(event: UserUpdatedEvent) -> None:
    await user_context.invalidate(event.user_id)
    logger.info("user_context.cache_invalidated", extra={"user_id": event.user_id})


event_bus.subscribe(UserUpdatedEvent, _on_user_updated)


# `datetime`은 DTO에서만 사용 — 명시적 import 유지
_ = datetime
