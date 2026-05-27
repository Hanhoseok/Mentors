from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from core.market_data.repository import MarketEntityMatch, find_entity_match


@dataclass(frozen=True)
class DebateTopicResolution:
    topic: str
    topic_type: str
    entity_symbol: str | None = None
    entity_name: str | None = None
    matched_text: str | None = None


async def resolve_with_market_data(
    raw_topic: str,
    db: AsyncSession,
) -> DebateTopicResolution | None:
    match = await find_entity_match(db, raw_topic)
    if not match:
        return None
    return _to_resolution(raw_topic, match)


def _to_resolution(raw_topic: str, match: MarketEntityMatch) -> DebateTopicResolution:
    entity = match.entity
    if entity.kind == "stock":
        normalized = _stock_topic(raw_topic, entity.name)
    elif entity.kind == "theme":
        normalized = _theme_topic(raw_topic, entity.name)
    else:
        normalized = raw_topic.strip()
    return DebateTopicResolution(
        topic=normalized,
        topic_type=entity.kind,
        entity_symbol=entity.symbol,
        entity_name=entity.name,
        matched_text=match.matched_text,
    )


def _stock_topic(raw_topic: str, name: str) -> str:
    compact = raw_topic.strip()
    if any(word in compact for word in ["실적", "주가", "배당", "오너리스크"]):
        return compact
    if re.search(r"팔까|팔아|팔아야|매도", compact):
        return f"{name} 주식 매도 판단"
    return f"{name} 주식 투자 전망"


def _theme_topic(raw_topic: str, name: str) -> str:
    compact = raw_topic.strip()
    if "리스크" in compact:
        return f"{name} 산업 성장성과 투자 리스크"
    if "관련주" in compact or "수혜주" in compact:
        return f"{name} 관련주 전망"
    return f"{name} 산업 전망과 투자 리스크"
