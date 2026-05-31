"""Google News RSS 수집기. 키워드 기반 검색.

newspipeline의 rss_collector.py에서 포팅 — async + Mentors 컨벤션.
"""

from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from ..schemas import ArticleRaw
from .base import BaseCollector

logger = logging.getLogger("content.collector.rss")

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
_LOCALES = [
    ("ko", "KR", "KR:ko"),
    ("en-US", "US", "US:en"),
]
_TIMEOUT_S = 15.0
_USER_AGENT = "Mozilla/5.0 (compatible; Mentors-Content/1.0)"


class GoogleNewsRSSCollector(BaseCollector):
    name = "google_news_rss"

    async def collect(self, keyword: str, max_items: int = 5) -> list[ArticleRaw]:
        results: list[ArticleRaw] = []
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            for hl, gl, ceid in _LOCALES:
                articles = await self._fetch_locale(client, keyword, hl, gl, ceid, max_items)
                results.extend(articles)
                if len(results) >= max_items:
                    break
        return results[:max_items]

    async def _fetch_locale(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        hl: str,
        gl: str,
        ceid: str,
        max_items: int,
    ) -> list[ArticleRaw]:
        query = f"{keyword} when:3d"
        params = f"?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"
        url = f"{_GOOGLE_NEWS_RSS}{params}"

        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(
                "content.rss_fetch_failed",
                extra={"keyword": keyword, "locale": ceid, "err": str(e)},
            )
            return []

        soup = BeautifulSoup(resp.text, "lxml-xml")
        out: list[ArticleRaw] = []
        for item in soup.find_all("item")[:max_items]:
            title = self._extract_text(item, "title")
            link = self._extract_text(item, "link")
            description = self._extract_text(item, "description")
            pub_date_raw = self._extract_text(item, "pubDate")
            source_el = item.find("source")
            source_name = source_el.get_text(strip=True) if source_el else "Google News"

            if not title or not link:
                continue

            out.append(
                ArticleRaw(
                    title=title,
                    url=link,
                    content=description,
                    source_name=source_name,
                    source_channel="rss",
                    published_at=self._parse_date(pub_date_raw),
                    language="ko" if hl.startswith("ko") else "en",
                    triggered_by_keywords=[keyword],
                )
            )
        return out

    @staticmethod
    def _extract_text(item: object, tag: str) -> str:
        el = getattr(item, "find", lambda *_: None)(tag)
        return el.get_text(strip=True) if el else ""

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
