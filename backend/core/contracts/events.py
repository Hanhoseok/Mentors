"""이벤트 카탈로그 (§6.2). 변경 시 PR 리뷰 + 영향 동 알림 (ADR-007)."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .enums import Tier
from .ids import ArticleId, ConceptId, DebateSessionId, MentorId, ReportId, SessionId, UserId


def _new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"


def _now() -> datetime:
    return datetime.now(UTC)


class BaseEvent(BaseModel):
    event_type: str
    event_id: str = Field(default_factory=_new_event_id)
    occurred_at: datetime = Field(default_factory=_now)
    user_id: UserId


# --- 코어 ---
class UserSignedUpEvent(BaseEvent):
    event_type: Literal["user.signed_up"] = "user.signed_up"


class UserUpdatedEvent(BaseEvent):
    event_type: Literal["user.updated"] = "user.updated"
    fields: list[str]


# --- 온보딩 ---
class OnboardingCompletedEvent(BaseEvent):
    event_type: Literal["onboarding.completed"] = "onboarding.completed"
    initial_tier: Tier = Tier.T1
    selected_mentor_id: MentorId | None = None


# --- 학습 ---
class MessageSentEvent(BaseEvent):
    event_type: Literal["learning.message_sent"] = "learning.message_sent"
    session_id: SessionId
    mentor_id: MentorId


class ConceptMasteredEvent(BaseEvent):
    event_type: Literal["learning.concept_mastered"] = "learning.concept_mastered"
    concept_id: ConceptId


# --- 성장 ---
class PromotionEligibleEvent(BaseEvent):
    """이해도 게이지 80% 도달 — FCM 푸시 트리거 (§6.6)."""

    event_type: Literal["growth.promotion_eligible"] = "growth.promotion_eligible"
    current_tier: Tier


class PromotionTestStartedEvent(BaseEvent):
    event_type: Literal["growth.promotion_test_started"] = "growth.promotion_test_started"
    target_tier: Tier


class PromotionTestPassedEvent(BaseEvent):
    event_type: Literal["growth.promotion_test_passed"] = "growth.promotion_test_passed"
    new_tier: Tier


# --- 토론 ---
class DebateCompletedEvent(BaseEvent):
    event_type: Literal["debate.completed"] = "debate.completed"
    debate_session_id: DebateSessionId


# --- 콘텐츠 ---
class ScrapAddedEvent(BaseEvent):
    event_type: Literal["content.scrap_added"] = "content.scrap_added"
    article_id: ArticleId


# --- 일일 리포트 ---
class DailyReportRequestedEvent(BaseEvent):
    """스케줄 트리거 → fan-out (ADR-013, AGENTS.md §5.7)."""

    event_type: Literal["daily_report.requested"] = "daily_report.requested"


class DailyReportGeneratedEvent(BaseEvent):
    event_type: Literal["daily_report.generated"] = "daily_report.generated"
    report_id: ReportId


__all__ = [
    "BaseEvent",
    "ConceptMasteredEvent",
    "DailyReportGeneratedEvent",
    "DailyReportRequestedEvent",
    "DebateCompletedEvent",
    "MessageSentEvent",
    "OnboardingCompletedEvent",
    "PromotionEligibleEvent",
    "PromotionTestPassedEvent",
    "PromotionTestStartedEvent",
    "ScrapAddedEvent",
    "UserSignedUpEvent",
    "UserUpdatedEvent",
]
