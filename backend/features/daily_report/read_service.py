"""DailyReportReader 구현 (AGENTS.md §5.2, ADR-014).

다른 동(학습)이 `from core.read_services import daily_report_reader`로 호출해
'그날 그 멘토 첫 진입'에서 오늘 리포트를 get-or-create 한다.

이 어댑터는 동 경계(읽기 DTO)만 담당하고, 실제 생성·멱등 로직은 service.py가
소유한다. ORM 모델(DailyReport)을 경계 밖으로 누설하지 않으려고 DailyReportRef로
변환해 돌려준다.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from core.contracts import MentorStrategy, ReportId, Tier, UserId
from core.read_services import DailyReportRef

from .models import DailyReport
from .service import get_or_create_today_report

logger = logging.getLogger("daily_report.read_service")


class DailyReportReadServiceImpl:
    """DailyReportReader Protocol 구현."""

    async def get_or_create_today_report(
        self, user_id: UserId, strategy: MentorStrategy
    ) -> DailyReportRef:
        report = await get_or_create_today_report(user_id, strategy)
        return self._to_ref(report)

    @staticmethod
    def _to_ref(report: DailyReport) -> DailyReportRef:
        try:
            highlights: list[dict[str, Any]] = json.loads(report.highlights_json or "[]")
        except json.JSONDecodeError:
            highlights = []
        return DailyReportRef(
            id=ReportId(report.id),
            report_date=report.report_date,
            mentor_strategy=MentorStrategy(report.mentor_strategy),
            tier=Tier(report.tier),
            status=report.status,
            body=report.body,
            highlights=highlights,
        )


__all__ = ["DailyReportReadServiceImpl"]
