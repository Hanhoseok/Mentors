"""APScheduler — 매일 오전 8시 (Asia/Seoul) 일일 리포트 fan-out.

스케줄 트리거 → EventBus fan-out → 핸들러 멱등 처리 (ADR-013, AGENTS.md §5.7).
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from core.auth.models import User
from core.contracts import DailyReportRequestedEvent, UserId
from core.db import SessionLocal
from core.event_bus import event_bus
from core.jobs import cron

logger = logging.getLogger("daily_report.jobs")


@cron("0 8 * * *", id="daily_report_dispatch")
async def dispatch_daily_reports() -> None:
    async with SessionLocal() as session:
        stmt = select(User.id).where(User.status == "active")
        rows = await session.execute(stmt)
        user_ids = [UserId(r[0]) for r in rows.all()]

    logger.info("daily_report.dispatch_start", extra={"user_count": len(user_ids)})

    now = datetime.now(UTC)
    for uid in user_ids:
        await event_bus.publish(DailyReportRequestedEvent(user_id=uid, occurred_at=now))
