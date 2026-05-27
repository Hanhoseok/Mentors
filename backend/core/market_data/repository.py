from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.market_data.models import MarketEntity, MarketNewsItem

SCORE_SUBSTRING = 100
SCORE_TOKEN_EXACT = 80
SCORE_TOKEN_PARTIAL = 30
MATCH_THRESHOLD = 30


@dataclass(frozen=True)
class MarketEntityMatch:
    entity: MarketEntity
    matched_text: str
    score: int


async def find_entity_match(db: AsyncSession, topic: str) -> MarketEntityMatch | None:
    tokens = _candidate_tokens(topic)
    if not tokens:
        return None

    candidate_filters = []
    for token in tokens[:6]:
        like = f"%{token}%"
        candidate_filters.extend(
            [
                MarketEntity.symbol.ilike(like),
                MarketEntity.name.ilike(like),
                MarketEntity.name_en.ilike(like),
            ]
        )
    result = await db.execute(select(MarketEntity).where(or_(*candidate_filters)).limit(50))
    candidates = list(result.scalars().all())
    if not candidates:
        result = await db.execute(select(MarketEntity).limit(200))
        candidates = list(result.scalars().all())

    scored = [
        match
        for entity in candidates
        if (match := _score_entity_match(entity, topic, tokens)) is not None
    ]
    if not scored:
        return None
    return max(scored, key=lambda match: match.score)


async def upsert_entity(
    db: AsyncSession,
    *,
    kind: str,
    symbol: str,
    name: str,
    name_en: str | None = None,
    exchange: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    aliases: list[str] | None = None,
    themes: list[str] | None = None,
    source: str = "manual",
    confidence: int = 100,
) -> MarketEntity:
    result = await db.execute(
        select(MarketEntity).where(MarketEntity.kind == kind, MarketEntity.symbol == symbol)
    )
    entity = result.scalar_one_or_none()
    if entity is None:
        entity = MarketEntity(kind=kind, symbol=symbol, name=name)
        db.add(entity)
    entity.name = name
    entity.name_en = name_en
    entity.exchange = exchange
    entity.sector = sector
    entity.industry = industry
    entity.aliases = aliases or []
    entity.themes = themes or []
    entity.source = source
    entity.confidence = confidence
    return entity


async def upsert_news_item(
    db: AsyncSession,
    entity: MarketEntity,
    *,
    title: str,
    source: str | None,
    url: str,
    summary: str | None,
    published_at: str | None,
) -> MarketNewsItem | None:
    if not url:
        return None
    result = await db.execute(
        select(MarketNewsItem).where(
            MarketNewsItem.entity_id == entity.id,
            MarketNewsItem.url == url,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = MarketNewsItem(entity=entity, url=url, title=title)
        db.add(item)
    item.title = title[:300]
    item.source = source
    item.summary = summary
    item.published_at = published_at
    return item


def _score_entity_match(
    entity: MarketEntity,
    topic: str,
    tokens: list[str],
) -> MarketEntityMatch | None:
    """Score entity names against a user topic.

    Direct substring and exact token matches are weighted high because they usually mean the
    user named a company/theme. Partial token matches are only a fallback and share the same
    value as the threshold, so a single weak signal can pass but never outrank explicit names.
    """

    compact = topic.lower()
    names = _matchable_entity_names(entity)
    best_text = ""
    best_score = 0
    for raw_name in names:
        name = str(raw_name).strip()
        if not name:
            continue
        name_key = name.lower()
        score = 0
        if name_key and name_key in compact:
            score += SCORE_SUBSTRING + min(len(name_key), SCORE_TOKEN_PARTIAL)
        if any(token.lower() == name_key for token in tokens):
            score += SCORE_TOKEN_EXACT
        elif any(token.lower() in name_key or name_key in token.lower() for token in tokens):
            score += SCORE_TOKEN_PARTIAL
        if score > best_score:
            best_score = score
            best_text = name
    if best_score < MATCH_THRESHOLD:
        return None
    return MarketEntityMatch(entity=entity, matched_text=best_text, score=best_score)


def _matchable_entity_names(entity: MarketEntity) -> list[str]:
    names = [
        entity.symbol,
        entity.name,
        entity.name_en or "",
        *(entity.aliases or []),
    ]
    if entity.kind != "stock":
        names.extend(entity.themes or [])
    return names


def _candidate_tokens(topic: str) -> list[str]:
    cleaned = re.sub(r"[^\w가-힣\s]", " ", topic)
    stopwords = {
        "지금",
        "전망",
        "투자",
        "주식",
        "관련주",
        "테마주",
        "수혜주",
        "살까",
        "팔까",
        "괜찮아",
        "괜찮나",
        "어때",
        "실적",
        "주가",
    }
    tokens = []
    for token in cleaned.split():
        token = token.strip()
        if len(token) < 2 or token in stopwords:
            continue
        tokens.append(token)
    return tokens
