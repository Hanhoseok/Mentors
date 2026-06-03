from __future__ import annotations

import asyncio
import logging
import re
import time
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from core.config import settings

logger = logging.getLogger("market_data.dart")

_DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
_TIMEOUT_S = 8.0
_STOCK_CACHE_TTL_S = 60 * 60 * 24
_STOCK_CODE_PATTERN = re.compile(r"^\d{6}$")


@dataclass(frozen=True)
class DartStock:
    code: str
    name: str
    corp_code: str
    market: str = "KRX"


class DartMarketDataClient:
    def __init__(self) -> None:
        self._stocks: list[DartStock] | None = None
        self._stocks_loaded_at: float | None = None
        self._lock = asyncio.Lock()

    async def search_stocks(self, query: str, *, limit: int = 5) -> list[DartStock]:
        if not query.strip() or not settings.dart_api_key:
            return []

        stocks = await self._load_stocks()
        query_key = _normalize(query)
        exact = [stock for stock in stocks if _normalize(stock.name) == query_key]
        partial = [
            stock
            for stock in stocks
            if stock not in exact
            and (query_key in _normalize(stock.name) or _normalize(stock.name) in query_key)
        ]
        return [*exact, *partial][:limit]

    async def _load_stocks(self) -> list[DartStock]:
        if self._is_cache_fresh():
            assert self._stocks is not None
            return self._stocks

        async with self._lock:
            if self._is_cache_fresh():
                assert self._stocks is not None
                return self._stocks

            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
                    response = await client.get(
                        _DART_CORP_CODE_URL,
                        params={"crtfc_key": settings.dart_api_key},
                    )
                    response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("dart.corp_code_failed", extra={"err": str(exc)})
                return []

            self._stocks = _parse_stocks(response.content)
            self._stocks_loaded_at = time.monotonic()
            return self._stocks

    def _is_cache_fresh(self) -> bool:
        if self._stocks is None or self._stocks_loaded_at is None:
            return False
        return time.monotonic() - self._stocks_loaded_at < _STOCK_CACHE_TTL_S


def _parse_stocks(payload: bytes | str, *, limit: int | None = None) -> list[DartStock]:
    xml_bytes = _extract_xml(payload)
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    stocks: list[DartStock] = []
    seen_codes: set[str] = set()
    for node in root.findall(".//list"):
        stock = _stock_from_node(node)
        if stock is None or stock.code in seen_codes:
            continue
        seen_codes.add(stock.code)
        stocks.append(stock)
        if limit is not None and len(stocks) >= limit:
            break
    return stocks


def _extract_xml(payload: bytes | str) -> bytes:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if zipfile.is_zipfile(BytesIO(raw)):
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            name = next(
                (filename for filename in archive.namelist() if filename.lower().endswith(".xml")),
                "",
            )
            if name:
                return archive.read(name)
    return raw


def _stock_from_node(node: Any) -> DartStock | None:
    corp_code = _node_text(node, "corp_code")
    name = _node_text(node, "corp_name")
    stock_code = _node_text(node, "stock_code")
    if not corp_code or not name or not _STOCK_CODE_PATTERN.fullmatch(stock_code):
        return None
    return DartStock(code=stock_code, name=name, corp_code=corp_code)


def _node_text(node: Any, tag: str) -> str:
    value = node.findtext(tag, default="")
    return " ".join(value.split())


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


dart_market_data = DartMarketDataClient()

__all__ = [
    "DartMarketDataClient",
    "DartStock",
    "dart_market_data",
]
