from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_tier: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="T1",
    )
    selected_mentor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    selected_mentor_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    risk_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    learning_goal: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    interests_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OnboardingSurveyAnswer(Base):
    __tablename__ = "onboarding_survey_answers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_code: Mapped[str] = mapped_column(String(100), nullable=False)
    question_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answer_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = ["OnboardingSurveyAnswer", "UserProfile"]
