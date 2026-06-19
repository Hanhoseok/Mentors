from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MentorCatalogEntry:
    id: int
    slug: str
    name: str
    title: str
    summary: str
    mentor_strategy: str
    experience_match: tuple[str, ...]
    risk_match: tuple[str, ...]
    goal_match: tuple[str, ...]
    interest_match: tuple[str, ...]
    style_match: tuple[str, ...]


MENTOR_CATALOG: tuple[MentorCatalogEntry, ...] = (
    MentorCatalogEntry(
        id=1,
        slug="warren-buffett",
        name="워런 버핏",
        title="가치 투자 멘토",
        summary="장기 복리, 밸류에이션 원칙, 그리고 기다림의 중요성을 설명합니다.",
        mentor_strategy="value",
        experience_match=("beginner", "steady-builder"),
        risk_match=("steady",),
        goal_match=("build-habit", "protect-capital"),
        interest_match=(
            "value",
            "dividend",
            "long-term",
            "fundamentals",
            "domestic-stock",
            "us-stock",
            "finance",
            "etf",
        ),
        style_match=("gentle", "patient"),
    ),
    MentorCatalogEntry(
        id=2,
        slug="peter-lynch",
        name="피터 린치",
        title="생활밀착형 종목 발굴 멘토",
        summary="실생활 사례를 바탕으로 기업을 읽는 법을 쉽게 설명합니다.",
        mentor_strategy="growth",
        experience_match=("beginner", "exploring"),
        risk_match=("balanced", "steady"),
        goal_match=("find-ideas", "understand-companies"),
        interest_match=(
            "stocks",
            "growth",
            "earnings",
            "consumer",
            "tech",
            "it",
            "bio",
            "domestic-stock",
            "us-stock",
            "semiconductor",
            "battery",
            "ai",
            "entertainment-media",
            "fashion-consumer",
        ),
        style_match=("practical", "friendly", "gentle"),
    ),
    MentorCatalogEntry(
        id=3,
        slug="john-bogle",
        name="존 보글",
        title="배당과 장기투자 멘토",
        summary="안정적인 배당과 현금흐름, 그리고 장기 투자의 복리 효과를 차분하게 설명합니다.",
        mentor_strategy="dividend",
        experience_match=("beginner", "steady-builder"),
        risk_match=("steady", "balanced"),
        goal_match=("protect-capital", "build-habit"),
        interest_match=(
            "dividend",
            "etf",
            "long-term",
            "fundamentals",
            "finance",
            "domestic-stock",
            "us-stock",
        ),
        style_match=("gentle", "patient"),
    ),
    MentorCatalogEntry(
        id=4,
        slug="mark-minervini",
        name="마크 미너비니",
        title="모멘텀 투자 멘토",
        summary="시장 주도주와 추세, 거래량을 읽고 손실을 제한하는 규율 있는 매매를 설명합니다.",
        mentor_strategy="momentum",
        experience_match=("exploring", "confident"),
        risk_match=("bold", "balanced"),
        goal_match=("find-style", "understand-news"),
        interest_match=(
            "crypto",
            "battery",
            "defense",
            "energy",
            "semiconductor",
            "ai",
            "us-stock",
            "domestic-stock",
        ),
        style_match=("challenging", "structured"),
    ),
)

_MENTOR_BY_ID = {entry.id: entry for entry in MENTOR_CATALOG}
_MENTOR_BY_SLUG = {entry.slug: entry for entry in MENTOR_CATALOG}


def list_catalog_mentors() -> tuple[MentorCatalogEntry, ...]:
    return MENTOR_CATALOG


def get_catalog_mentor_by_id(mentor_id: int) -> MentorCatalogEntry | None:
    return _MENTOR_BY_ID.get(mentor_id)


def get_catalog_mentor_by_slug(slug: str | None) -> MentorCatalogEntry | None:
    if slug is None:
        return None
    return _MENTOR_BY_SLUG.get(slug)


__all__ = [
    "MentorCatalogEntry",
    "get_catalog_mentor_by_id",
    "get_catalog_mentor_by_slug",
    "list_catalog_mentors",
]
