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
        name="Warren Buffett",
        title="Value Investing Mentor",
        summary="Long-term compounding, valuation discipline, and patience.",
        mentor_strategy="value",
        experience_match=("beginner", "steady-builder"),
        risk_match=("steady",),
        goal_match=("build-habit", "protect-capital"),
        interest_match=("value", "dividend", "long-term", "fundamentals"),
        style_match=("gentle", "patient"),
    ),
    MentorCatalogEntry(
        id=2,
        slug="peter-lynch",
        name="Peter Lynch",
        title="Everyday Stock Picking Mentor",
        summary="Company-first research with practical examples and accessible explanations.",
        mentor_strategy="growth",
        experience_match=("beginner", "exploring"),
        risk_match=("balanced", "steady"),
        goal_match=("find-ideas", "understand-companies"),
        interest_match=("stocks", "growth", "earnings", "consumer"),
        style_match=("practical", "friendly", "gentle"),
    ),
    MentorCatalogEntry(
        id=3,
        slug="ray-dalio",
        name="Ray Dalio",
        title="Macro and Portfolio Mentor",
        summary="Macro frameworks, diversification, and structured decision making.",
        mentor_strategy="macro",
        experience_match=("exploring", "experienced"),
        risk_match=("balanced", "dynamic"),
        goal_match=("understand-news", "build-allocation"),
        interest_match=("macro", "etf", "diversification", "portfolio"),
        style_match=("structured", "analytical"),
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
