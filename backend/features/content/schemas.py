"""콘텐츠 동 Pydantic v2 스키마 (HTTP 입출력 전용).

규칙:
  - SQLAlchemy 모델과 분리. ORM 객체를 직접 노출 금지 — 항상 from_attributes로 변환.
  - 다른 동 import 금지 — 노출 필요 시 core.read_services 프로토콜 갱신 PR.
"""

from __future__ import annotations

import html as _html
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from core.contracts import MentorStrategy


# ---------------------------------------------------------------------------
# 수집 원본 (내부 전용 — 외부 노출 X)
# ---------------------------------------------------------------------------


class ArticleRaw(BaseModel):
    """수집기 → service.ingest_articles()로 흘러가는 표준 입력."""

    title: str
    url: str
    content: str | None = None
    source_name: str | None = None
    source_channel: str | None = None
    published_at: datetime | None = None
    language: str = "en"
    image_url: str | None = None
    triggered_by_keywords: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AI 처리 결과 (내부 전용)
# ---------------------------------------------------------------------------


class AIProcessingResult(BaseModel):
    status: Literal["completed", "failed", "skipped"] = "completed"
    translated_title_ko: str | None = None
    translated_content_ko: str | None = None
    summary_ko: str | None = None
    keywords: list[str] = Field(default_factory=list)
    sentiment: Literal["positive", "neutral", "negative"] | None = None
    investment_relevance: Literal["high", "medium", "low"] | None = None
    strategies: list[MentorStrategy] = Field(default_factory=list)
    detected_language: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# API 응답 (라우터에서 사용)
# ---------------------------------------------------------------------------


def _decode_entities(s: str | None) -> str | None:
    if not s:
        return s
    out = _html.unescape(s)
    if "&" in out and ";" in out:
        out = _html.unescape(out)
    return out


class NewsArticleResponse(BaseModel):
    """사용자 노출용 기사. ORM → from_attributes로 변환."""

    id: int
    title_original: str
    title_translated: str | None = None
    summary_ko: str | None = None
    content: str | None = None
    content_translated: str | None = None
    original_url: str
    source_name: str | None = None
    image_url: str | None = None
    language: str
    published_at: datetime | None = None
    reliability_score: int
    reliability_level: str
    composite_score: float = 0.0
    strategies: list[MentorStrategy] = Field(default_factory=list)
    ai_sentiment: str | None = None
    ai_investment_relevance: str | None = None
    keywords: list[str] = Field(default_factory=list)
    # AI 처리 상태: pending|processing|completed|skipped|failed
    # ('skipped'/'failed'면 요약이 영영 생성되지 않으므로 프론트가 정직하게 안내)
    ai_processing_status: str | None = None

    # 편의 필드 (computed)
    display_title: str | None = None
    display_summary: str | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _from_orm_strategies(cls, data: Any) -> Any:
        """ORM에서 strategies(콤마 문자열) → list[MentorStrategy] 변환."""
        if hasattr(data, "strategies"):  # ORM object
            raw = data.strategies or ""
            data = {
                **{c.name: getattr(data, c.name) for c in data.__table__.columns},
                "strategies": [s for s in raw.split(",") if s],
                "keywords": cls._parse_keywords(getattr(data, "ai_keywords", None)),
            }
        return data

    @staticmethod
    def _parse_keywords(raw: Any) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw][:5]
        try:
            parsed = json.loads(raw)
            return [str(x) for x in parsed][:5] if isinstance(parsed, list) else []
        except Exception:
            return [p.strip() for p in str(raw).split(",") if p.strip()][:5]

    @model_validator(mode="after")
    def _populate_display(self) -> "NewsArticleResponse":
        self.title_original = _decode_entities(self.title_original) or self.title_original
        self.title_translated = _decode_entities(self.title_translated)
        self.summary_ko = _decode_entities(self.summary_ko)
        self.content = _decode_entities(self.content)
        self.content_translated = _decode_entities(self.content_translated)
        self.display_title = self.title_translated or self.title_original
        self.display_summary = self.summary_ko
        return self


class NewsListResponse(BaseModel):
    items: list[NewsArticleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SearchHit(BaseModel):
    article_id: int
    score: float
    title: str
    summary: str | None
    source_name: str | None
    url: str
    image_url: str | None
    matched_chunk: str
    published_at: datetime | None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchHit]


# ---------------------------------------------------------------------------
# 스크랩 폴더
# ---------------------------------------------------------------------------


class ScrapFolderCreateRequest(BaseModel):
    """폴더 생성 요청. user_id는 get_current_user에서 주입.

    name 최대 길이는 프론트 TextInput(maxLength=30)과 맞춘다. DB 컬럼은
    String(100)이라 여유가 있지만, 입력 검증은 30자로 통일.
    """

    name: str = Field(min_length=1, max_length=30)
    color: str | None = Field(default=None, max_length=20)


class ScrapFolderResponse(BaseModel):
    id: int
    user_id: int
    name: str
    color: str | None = None
    scrap_count: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}


class ScrapCreateRequest(BaseModel):
    """스크랩 생성 요청.

    article_id는 선택 — 실시간 RSS 기사처럼 DB에 없는 경우 스냅샷만으로 저장한다.
    folder_id가 없으면 미분류 스크랩.
    """

    folder_id: int | None = None
    article_id: int | None = None
    title: str = Field(min_length=1, max_length=1000)
    url: str = Field(min_length=1, max_length=2000)
    image_url: str | None = None
    summary: str | None = None
    source_name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    published_at: datetime | None = None


class ScrapExistsResponse(BaseModel):
    """특정 기사(article_id 또는 url)의 스크랩 여부 단건 조회 결과.

    전체 목록을 받아 클라이언트에서 매칭하면 limit 상한에 걸려 누락될 수 있어,
    서버에서 EXISTS로 정확히 판정한다.
    """

    exists: bool


class ScrapResponse(BaseModel):
    id: int
    user_id: int
    folder_id: int | None = None
    article_id: int | None = None
    title: str
    url: str
    image_url: str | None = None
    summary: str | None = None
    source_name: str | None = None
    category: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 사용자별 관심 키워드 — /api/content/keywords
# ---------------------------------------------------------------------------


class UserKeywordCreateRequest(BaseModel):
    """사용자 관심 키워드 추가 요청.

    user_id는 받지 않는다 — get_current_user에서 주입.
    """

    keyword: str = Field(min_length=1, max_length=200)
    language: str = Field(default="auto", max_length=10)


class UserKeywordResponse(BaseModel):
    """사용자의 관심 키워드 항목.

    `keyword`/`language`는 연결된 MasterKeyword에서 가져옴.
    """

    id: int
    keyword: str
    language: str
    source: str
    weight: int
    master_keyword_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _from_orm(cls, data: Any) -> Any:
        # UserKeyword ORM 객체 → flatten (master_keyword.keyword/language 끌어올림)
        if hasattr(data, "master_keyword") and hasattr(data, "id"):
            mk = data.master_keyword
            return {
                "id": data.id,
                "keyword": mk.keyword if mk is not None else "",
                "language": mk.language if mk is not None else "auto",
                "source": data.source,
                "weight": data.weight,
                "master_keyword_id": data.master_keyword_id,
                "created_at": data.created_at,
            }
        return data


class UserKeywordListResponse(BaseModel):
    items: list[UserKeywordResponse]
    total: int


# ---------------------------------------------------------------------------
# 실시간 토픽 뉴스 — /api/content/news/live-topics
# 파이프라인 우회. 신뢰도 필터/DB 저장 없음. Google News RSS + OpenAI 요약.
# ---------------------------------------------------------------------------


class LiveTopicNewsItem(BaseModel):
    title: str
    url: str
    source_name: str | None = None
    published_at: datetime | None = None
    language: str = "ko"
    summary_ko: str
    image_url: str | None = None
    keywords: list[str] = Field(default_factory=list)


class LiveTopicNewsResponse(BaseModel):
    topic: str
    items: list[LiveTopicNewsItem]


# ---------------------------------------------------------------------------
# 산업 분류 + 하위 키워드 — /api/content/industries
# ---------------------------------------------------------------------------


class IndustryKeywordItem(BaseModel):
    id: int
    label_ko: str
    keyword_en: str
    display_order: int

    model_config = {"from_attributes": True}


class IndustryItem(BaseModel):
    id: int
    name_ko: str
    name_en: str
    display_order: int
    keywords: list[IndustryKeywordItem] = Field(default_factory=list)

    model_config = {"from_attributes": True}


__all__ = [
    "AIProcessingResult",
    "ArticleRaw",
    "IndustryItem",
    "IndustryKeywordItem",
    "LiveTopicNewsItem",
    "LiveTopicNewsResponse",
    "NewsArticleResponse",
    "NewsListResponse",
    "ScrapCreateRequest",
    "ScrapFolderCreateRequest",
    "ScrapFolderResponse",
    "ScrapResponse",
    "SearchHit",
    "SearchResponse",
    "UserKeywordCreateRequest",
    "UserKeywordListResponse",
    "UserKeywordResponse",
]
