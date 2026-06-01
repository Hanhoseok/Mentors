"""뉴스 수집기. 외부 API는 콘텐츠 동 자체 사용 — 코어 래퍼 불필요 (AGENTS.md
features/content/__init__.py 주석 참조)."""

from .base import BaseCollector
from .finnhub import FinnhubCollector
from .rss import GoogleNewsRSSCollector

__all__ = ["BaseCollector", "FinnhubCollector", "GoogleNewsRSSCollector"]
