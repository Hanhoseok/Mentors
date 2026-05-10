from datetime import datetime

from pydantic import BaseModel

from core.contracts import MentorId, Tier, UserId, UserStatus


class UserContextBase(BaseModel):
    user_id: UserId
    nickname: str
    tier: Tier
    status: UserStatus


class MentorChatContext(UserContextBase):
    interests: list[str]
    selected_mentor_id: MentorId | None


class DailyReportContext(UserContextBase):
    today_chat_count: int
    today_scrap_count: int


class PromotionTestContext(UserContextBase):
    chat_count_this_week: int
    last_promotion_attempt_at: datetime | None


class DebateContext(UserContextBase):
    interests: list[str]


__all__ = [
    "DailyReportContext",
    "DebateContext",
    "MentorChatContext",
    "PromotionTestContext",
    "UserContextBase",
]
