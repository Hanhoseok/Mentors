from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class DailyReportCore(Base):
    """사용자×날짜 1회 생성되는 공통 시장 코어 (멘토 무관).

    멘토별 리포트(DailyReport)들이 이 코어를 공유한다. cron 또는 그날 첫 진입 시
    한 번만 생성되고, 이후 멘토 렌즈 레이어(DailyReport)가 lazy로 붙는다.
    이렇게 분리해야 멘토를 늦게 처음 여는 경우에도 시장 요약을 재계산하지 않는다.
    """

    __tablename__ = "daily_report_cores"
    __table_args__ = (
        UniqueConstraint("user_id", "report_date", name="uq_daily_report_cores_user_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 그날 사용자에게 선별된 뉴스 id 목록 (JSON 직렬화된 list[int]).
    news_ids_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    # 멘토 무관 중립 시장 요약 (LLM 생성 전엔 NULL).
    market_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 그날 연결할 학습 개념 (없으면 NULL).
    today_concept_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
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


class DailyReport(Base):
    """멘토 전략별 일일 리포트 (user × mentor_strategy × date).

    공통 코어(DailyReportCore)를 전략 렌즈로 재해석한 결과물. status로
    pending/ready/failed 생애주기를 표현하며, 멱등 upsert 키는
    (user_id, mentor_strategy, report_date)다. body/highlights는 생성 전
    NULL(스켈레톤) 상태로 먼저 행이 잡힐 수 있다.
    """

    __tablename__ = "daily_reports"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "mentor_strategy",
            "report_date",
            name="uq_daily_reports_user_strategy_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # 공유 코어 참조. 코어가 지워져도 리포트 본문은 남도록 SET NULL.
    core_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("daily_report_cores.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    # MentorStrategy 값 (value/growth/dividend/momentum).
    mentor_strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    # 생성 시점 사용자 티어 (T1~T5) — 리포트 깊이 기록용.
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    # 생애주기: pending(스켈레톤) → ready(생성 완료) → failed(생성 실패).
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    # 멘토 렌즈로 작성된 리포트 본문 (마크다운) — 생성 전엔 NULL.
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 하이라이트 (JSON: list[{news_id, lens}]) — 생성 전엔 NULL.
    highlights_json: Mapped[str | None] = mapped_column(Text, nullable=True)
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


__all__ = ["DailyReport", "DailyReportCore"]
