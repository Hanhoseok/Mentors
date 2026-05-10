"""6동 — 일일 리포트.

owner: TODO
관련 FR: FR-03, UC-02
이벤트: DailyReportRequestedEvent (구독), DailyReportGeneratedEvent (발행)
스케줄: 매일 8시 (Asia/Seoul) cron — features/daily_report/jobs.py
"""

from fastapi import APIRouter, Depends

from core.auth.dependencies import get_current_user
from core.auth.models import User

router = APIRouter(prefix="/api/daily-report", tags=["daily-report"])


@router.get("/today")
async def today_report(user: User = Depends(get_current_user)) -> dict[str, str | None]:
    # TODO: 오늘 날짜의 DailyReport 조회 (daily_reports 테이블 — 본 동에서 추가)
    return {"report": None, "user_id": str(user.id)}
