from __future__ import annotations

from typing import TypedDict


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
