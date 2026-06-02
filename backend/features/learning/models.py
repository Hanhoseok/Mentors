"""학습 동 DB 모델 — 멘토 채팅 세션 + 메시지.

owner: learning
관련 FR: FR-02, UC-04, UC-10
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class ChatSession(Base):
    """멘토 채팅 세션."""

    __tablename__ = "learning_chat_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mentor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """채팅 메시지 (사용자 + 멘토 응답 모두 저장)."""

    __tablename__ = "learning_chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("learning_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class LearningQuizProgress(Base):
    __tablename__ = "learning_quiz_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "question_id",
            name="uq_learning_quiz_progress_user_question",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False)
    concept_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    last_answer_index: Mapped[int] = mapped_column(Integer, nullable=False)
    last_result_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    solved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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


class DailyOpenerLog(Base):
    """그날 그 멘토 첫 진입 dedup 마커.

    (user_id, mentor_id, opened_date) 자연키. 첫 진입 시 ON CONFLICT DO NOTHING
    upsert로 1행만 남기고, RETURNING으로 '이번 호출이 첫 진입인지'를 판정해
    일일 리포트 카드를 하루 한 번만 노출한다.
    """

    __tablename__ = "learning_daily_openers"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "mentor_id",
            "opened_date",
            name="uq_learning_daily_openers_user_mentor_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mentor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    opened_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
