from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai_pipeline.news_search import news_search
from core.db import transaction
from core.exceptions import ExternalServiceError
from core.market_data.models import MarketEntity
from core.market_data.repository import upsert_entity, upsert_news_item

logger = logging.getLogger("market_data")


class SeedEntity(TypedDict, total=False):
    kind: str
    symbol: str
    name: str
    name_en: str
    exchange: str
    sector: str
    industry: str
    aliases: list[str]
    themes: list[str]


DEFAULT_SEED_ENTITIES: tuple[SeedEntity, ...] = (
    {
        "kind": "stock",
        "symbol": "PLTR",
        "name": "팔란티어",
        "name_en": "Palantir",
        "exchange": "NYSE",
        "sector": "software",
        "industry": "data analytics",
        "aliases": ["palantir", "pltr"],
        "themes": ["AI", "방산", "데이터 분석"],
    },
    {
        "kind": "stock",
        "symbol": "RBLX",
        "name": "로블록스",
        "name_en": "Roblox",
        "exchange": "NYSE",
        "sector": "communication services",
        "industry": "gaming platform",
        "aliases": ["roblox", "rblx"],
        "themes": ["게임", "메타버스"],
    },
    {
        "kind": "theme",
        "symbol": "SPACE_TECH",
        "name": "우주테크",
        "name_en": "space tech",
        "sector": "industrial technology",
        "aliases": ["우주항공", "항공우주", "위성", "발사체", "space economy"],
        "themes": ["방산", "위성통신", "발사체"],
    },
    {
        "kind": "theme",
        "symbol": "QUANTUM_COMPUTING",
        "name": "양자컴퓨팅",
        "name_en": "quantum computing",
        "sector": "technology",
        "aliases": ["양자컴퓨터", "퀀텀컴퓨팅", "quantum"],
        "themes": ["반도체", "클라우드", "보안"],
    },
    {
        "kind": "theme",
        "symbol": "POWER_GRID",
        "name": "전력망",
        "name_en": "power grid",
        "sector": "infrastructure",
        "aliases": ["송전망", "전력 인프라", "grid infrastructure"],
        "themes": ["전력", "AI 데이터센터", "인프라"],
    },
)


async def refresh_market_data() -> None:
    async with transaction() as db:
        await seed_market_entities(db)
        await refresh_tracked_entity_news(db)


async def seed_market_entities(db: AsyncSession) -> None:
    for seed in DEFAULT_SEED_ENTITIES:
        await upsert_entity(
            db,
            kind=seed["kind"],
            symbol=seed["symbol"],
            name=seed["name"],
            name_en=seed.get("name_en"),
            exchange=seed.get("exchange"),
            sector=seed.get("sector"),
            industry=seed.get("industry"),
            aliases=seed.get("aliases", []),
            themes=seed.get("themes", []),
            source="seed",
            confidence=90,
        )


async def refresh_tracked_entity_news(db: AsyncSession, limit: int = 30) -> int:
    result = await db.execute(select(MarketEntity).order_by(MarketEntity.id).limit(limit))
    entities = list(result.scalars().all())
    refreshed = 0
    for entity in entities:
        query = _entity_news_query(entity)
        try:
            documents = await news_search.search(query, top_k=3)
        except ExternalServiceError:
            logger.warning("market_data.news_refresh_failed", extra={"entity": entity.symbol})
            continue
        for doc in documents:
            await upsert_news_item(
                db,
                entity,
                title=str(doc.metadata.get("title") or doc.text[:120]),
                source=str(doc.metadata.get("source") or ""),
                url=str(doc.metadata.get("url") or ""),
                summary=doc.text,
                published_at=str(doc.metadata.get("published_at") or ""),
            )
        entity.last_refreshed_at = datetime.now(UTC)
        refreshed += 1
    return refreshed


def _entity_news_query(entity: MarketEntity) -> str:
    if entity.kind == "stock":
        return f"{entity.name} {entity.symbol} 실적 주가 전망"
    return f"{entity.name} 관련주 산업 전망 투자 리스크"
