"""Finnhub 회사 뉴스 수집기. 키워드를 ticker로 해석하여 회사 뉴스 가져옴.

회사명 → ticker 해석은 별도 resolver(현재 미구현)가 필요. 본 수집기는
keyword가 이미 ticker(예: "AAPL", "NVDA")일 때 동작. 그 외엔 빈 리스트.

settings.finnhub_api_key가 없으면 비활성.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx

from core.config import settings

from ..schemas import ArticleRaw
from .base import BaseCollector

logger = logging.getLogger("content.collector.finnhub")

_FINNHUB_COMPANY_NEWS = "https://finnhub.io/api/v1/company-news"
_TIMEOUT_S = 10.0
_LOOKBACK_DAYS = 3


class FinnhubCollector(BaseCollector):
    name = "finnhub"

    @property
    def enabled(self) -> bool:
        return bool(getattr(settings, "finnhub_api_key", None))

    async def collect(self, keyword: str, max_items: int = 5) -> list[ArticleRaw]:
        if not self.enabled:
            return []

        # heuristic: ticker가 짧고 대문자만이면 회사 뉴스 호출, 아니면 skip
        if not (keyword.isupper() and 1 < len(keyword) <= 5):
            return []

        to = datetime.now(UTC).date()
        frm = to - timedelta(days=_LOOKBACK_DAYS)
        params = {
            "symbol": keyword,
            "from": frm.isoformat(),
            "to": to.isoformat(),
            "token": settings.finnhub_api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                resp = await client.get(_FINNHUB_COMPANY_NEWS, params=params)
                resp.raise_for_status()
                items = resp.json()
        except httpx.HTTPError as e:
            logger.warning("content.finnhub_failed", extra={"ticker": keyword, "err": str(e)})
            return []
        except ValueError:
            return []

        out: list[ArticleRaw] = []
        for item in items[:max_items]:
            headline = (item.get("headline") or "").strip()
            url = (item.get("url") or "").strip()
            if not headline or not url:
                continue
            published_at: datetime | None = None
            ts = item.get("datetime")
            if isinstance(ts, (int, float)):
                published_at = datetime.fromtimestamp(int(ts), tz=UTC)
            out.append(
                ArticleRaw(
                    title=headline,
                    url=url,
                    content=(item.get("summary") or "").strip() or None,
                    source_name=(item.get("source") or "").strip() or "Finnhub",
                    source_channel="api",
                    published_at=published_at,
                    image_url=(item.get("image") or "").strip() or None,
                    language="en",
                    triggered_by_keywords=[keyword],
                )
            )
        return out
