"""Read facade for cross-feature user context."""

import json
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
from features.onboarding.models import UserProfile

from .dto import (
    DailyReportContext,
    DebateContext,
    MentorChatContext,
    PromotionTestContext,
    UserContextBase,
)

logger = logging.getLogger("user_context")
_CACHE_TTL = 300


class UserContextService:
    def __init__(self) -> None:
        self._cache = make_cache("user_context")

    async def get_tier(self, user_id: UserId) -> Tier:
        profile = await self._load_profile(user_id)
        if profile is None or not profile.current_tier:
            return Tier.T1
        try:
            return Tier(profile.current_tier)
        except ValueError:
            logger.warning(
                "user_context.invalid_tier",
                extra={"user_id": user_id, "tier": profile.current_tier},
            )
            return Tier.T1

    async def get_interests(self, user_id: UserId) -> list[str]:
        profile = await self._load_profile(user_id)
        return self._deserialize_interests(
            profile.interests_json if profile is not None else None
        )

    async def get_status(self, user_id: UserId) -> UserStatus:
        user = await self._load_user(user_id)
        return UserStatus(user.status)

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
            today_chat_count=0,
            today_scrap_count=0,
        )

    async def get_for_promotion_test(self, user_id: UserId) -> PromotionTestContext:
        base = await self._load_base(user_id)
        return PromotionTestContext(
            **base.model_dump(),
            chat_count_this_week=0,
            last_promotion_attempt_at=None,
        )

    async def get_for_debate(self, user_id: UserId) -> DebateContext:
        base = await self._load_base(user_id)
        return DebateContext(
            **base.model_dump(),
            interests=await self.get_interests(user_id),
        )

    async def invalidate(self, user_id: UserId) -> None:
        await self._cache.delete(f"base:{user_id}")
        await self._cache.delete(f"tier:{user_id}")
        await self._cache.delete(f"interests:{user_id}")

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

    async def _load_profile(self, user_id: UserId) -> UserProfile | None:
        async with SessionLocal() as session:
            return await session.get(UserProfile, int(user_id))

    async def _get_selected_mentor(self, user_id: UserId) -> MentorId | None:
        profile = await self._load_profile(user_id)
        if profile is None or profile.selected_mentor_id is None:
            return None
        return MentorId(profile.selected_mentor_id)

    def _deserialize_interests(self, raw_interests: str | None) -> list[str]:
        if not raw_interests:
            return []
        try:
            decoded = json.loads(raw_interests)
        except json.JSONDecodeError:
            logger.warning("user_context.invalid_interests_payload")
            return []
        if not isinstance(decoded, list):
            return []

        interests: list[str] = []
        for value in decoded:
            if isinstance(value, str) and value not in interests:
                interests.append(value)
        return interests


user_context = UserContextService()


async def _on_user_updated(event: UserUpdatedEvent) -> None:
    await user_context.invalidate(event.user_id)
    logger.info("user_context.cache_invalidated", extra={"user_id": event.user_id})


event_bus.subscribe(UserUpdatedEvent, _on_user_updated)
_ = datetime
