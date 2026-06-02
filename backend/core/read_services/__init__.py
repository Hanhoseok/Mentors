"""Read services 코어 모듈. AGENTS.md §5.2."""

from typing import Any, cast

from .protocols import (
    ContentReader,
    DailyReportReader,
    DailyReportRef,
    GrowthReader,
    NewsRef,
)
from .registry import (
    get_content_reader,
    get_daily_report_reader,
    get_growth_reader,
    register_content_reader,
    register_daily_report_reader,
    register_growth_reader,
)


class _LazyReaderProxy:
    """모듈 import 시점에는 reader가 아직 등록 안 됐을 수 있으므로,
    실제 호출 시점에 registry에서 resolve 한다."""

    def __init__(self, getter: Any) -> None:
        self._getter = getter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._getter(), name)


content_reader: ContentReader = cast(ContentReader, _LazyReaderProxy(get_content_reader))
growth_reader: GrowthReader = cast(GrowthReader, _LazyReaderProxy(get_growth_reader))
daily_report_reader: DailyReportReader = cast(
    DailyReportReader, _LazyReaderProxy(get_daily_report_reader)
)


__all__ = [
    "ContentReader",
    "DailyReportReader",
    "DailyReportRef",
    "GrowthReader",
    "NewsRef",
    "content_reader",
    "daily_report_reader",
    "get_content_reader",
    "get_daily_report_reader",
    "get_growth_reader",
    "growth_reader",
    "register_content_reader",
    "register_daily_report_reader",
    "register_growth_reader",
]
