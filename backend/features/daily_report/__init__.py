"""일일 리포트 동 — 시범 PR (cron + EventBus fan-out + ContentReader + Push 통합).

앱 시작 시:
- jobs.py import → @cron으로 APScheduler에 dispatch_daily_reports 등록
- handlers.py import → EventBus 구독 등록
"""

from core.contracts import DailyReportRequestedEvent
from core.event_bus import event_bus

from . import jobs  # noqa: F401  (cron 등록 트리거)
from .handlers import on_daily_report_requested
from .router import router

event_bus.subscribe(DailyReportRequestedEvent, on_daily_report_requested)

__all__ = ["router"]
