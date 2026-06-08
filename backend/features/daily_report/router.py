"""6동 — 일일 리포트.

owner: TODO
관련 FR: FR-03, UC-02
이벤트: DailyReportRequestedEvent (구독), DailyReportGeneratedEvent (발행)
스케줄: 매일 8시 (Asia/Seoul) cron — features/daily_report/jobs.py
"""

import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.contracts import UserId
from core.db import get_db
from core.exceptions import NotFoundError

from .models import DailyReport
from .service import get_or_create_today_report, resolve_strategy

router = APIRouter(prefix="/api/daily-report", tags=["daily-report"])


class DailyReportOut(BaseModel):
    id: int
    report_date: date
    mentor_strategy: str
    tier: str
    status: str
    body: str | None
    highlights: list[dict[str, Any]]


def _serialize(report: DailyReport) -> DailyReportOut:
    try:
        highlights = json.loads(report.highlights_json or "[]")
    except json.JSONDecodeError:
        highlights = []
    return DailyReportOut(
        id=report.id,
        report_date=report.report_date,
        mentor_strategy=report.mentor_strategy,
        tier=report.tier,
        status=report.status,
        body=report.body,
        highlights=highlights,
    )


@router.get("/me/history")
async def my_report_history(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DailyReportOut]:
    """내 일일 리포트 목록 (최근 순)."""
    reports = (
        await db.execute(
            select(DailyReport)
            .where(DailyReport.user_id == int(user.id), DailyReport.status == "ready")
            .order_by(DailyReport.report_date.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_serialize(r) for r in reports]


@router.get("/today")
async def today_report(user: User = Depends(get_current_user)) -> DailyReportOut:
    """그날 첫 진입 — 선택 멘토 전략의 오늘 리포트를 get-or-create 해서 반환.

    아직 없으면 이 호출에서 동기 생성한다(lazy). 스켈레톤·비동기화는 Phase 4.
    """
    user_id = UserId(user.id)
    strategy = await resolve_strategy(user_id)
    report = await get_or_create_today_report(user_id, strategy)
    return _serialize(report)


@router.get("/{report_id}")
async def report_detail(
    report_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyReportOut:
    report = await db.scalar(
        select(DailyReport).where(
            DailyReport.id == report_id,
            DailyReport.user_id == int(user.id),
        )
    )
    if report is None:
        raise NotFoundError("Daily report not found.")
    return _serialize(report)
