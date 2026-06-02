"""Reader 레지스트리. 동의 구현체를 등록·조회.

사용:
    # features/content/__init__.py (등록)
    from core.read_services import register_content_reader
    from .read_service import ContentReadServiceImpl
    register_content_reader(ContentReadServiceImpl())

    # 다른 동에서 (소비)
    from core.read_services import content_reader
    news = await content_reader.get_today_news_for_user(uid)
"""

from .protocols import ContentReader, DailyReportReader, GrowthReader

_content_reader: ContentReader | None = None
_growth_reader: GrowthReader | None = None
_daily_report_reader: DailyReportReader | None = None


def register_content_reader(impl: ContentReader) -> None:
    global _content_reader
    _content_reader = impl


def get_content_reader() -> ContentReader:
    if _content_reader is None:
        raise RuntimeError(
            "ContentReader not registered. "
            "Add `register_content_reader(...)` to features/content/__init__.py"
        )
    return _content_reader


def register_growth_reader(impl: GrowthReader) -> None:
    global _growth_reader
    _growth_reader = impl


def get_growth_reader() -> GrowthReader:
    if _growth_reader is None:
        raise RuntimeError(
            "GrowthReader not registered. "
            "Add `register_growth_reader(...)` to features/growth/__init__.py"
        )
    return _growth_reader


def register_daily_report_reader(impl: DailyReportReader) -> None:
    global _daily_report_reader
    _daily_report_reader = impl


def get_daily_report_reader() -> DailyReportReader:
    if _daily_report_reader is None:
        raise RuntimeError(
            "DailyReportReader not registered. "
            "Add `register_daily_report_reader(...)` to features/daily_report/__init__.py"
        )
    return _daily_report_reader


__all__ = [
    "get_content_reader",
    "get_daily_report_reader",
    "get_growth_reader",
    "register_content_reader",
    "register_daily_report_reader",
    "register_growth_reader",
]
