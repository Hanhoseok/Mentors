"""수집기 베이스. 모든 수집기는 ArticleRaw 리스트를 반환."""

from __future__ import annotations

import abc
import logging

from ..schemas import ArticleRaw

logger = logging.getLogger("content.collector")


class BaseCollector(abc.ABC):
    """수집기 인터페이스. 한 키워드 → ArticleRaw 리스트."""

    name: str = "base"

    @abc.abstractmethod
    async def collect(self, keyword: str, max_items: int = 5) -> list[ArticleRaw]:
        """주어진 키워드로 외부 소스에서 기사 수집. 실패 시 빈 리스트 반환."""

    async def collect_safe(self, keyword: str, max_items: int = 5) -> list[ArticleRaw]:
        """예외 삼킴 wrapper — 한 키워드 실패가 전체 tick을 죽이지 않게."""
        try:
            return await self.collect(keyword, max_items=max_items)
        except Exception:
            logger.exception(
                "content.collect_failed", extra={"collector": self.name, "keyword": keyword}
            )
            return []
