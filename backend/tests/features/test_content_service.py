"""콘텐츠 동 ContentService._persist_articles dedup 로직 단위 테스트.

PR-Ⅱ에서 도입된 2-pass dedup:
  1차: raw.url canonical로 NewsArticle 매칭 → fetch 자체를 회피 (외부 호출 절약)
  2차: ContentExtractor.extract()가 돌려준 resolved_url canonical로 다시 매칭
       → Google News interstitial 등 같은 publisher 기사를 가리키는 서로 다른
         redirect URL을 두 번째 row로 저장하지 않도록 fetch 후 한 번 더 체크

테스트는 AsyncSession과 content_extractor를 fake로 대체하여 외부 의존 0.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from features.content import pipeline_utils as pu
from features.content.models import ArticleKeyword, MasterKeyword, NewsArticle
from features.content.schemas import ArticleRaw
from features.content.service import ContentService

# ---------------------------------------------------------------------------
# Fake helpers — AsyncSession 흉내
# ---------------------------------------------------------------------------


def _entity_name(stmt: Any) -> str:
    """`select(X)`의 X 클래스 이름 추출 — scalar 호출 라우팅용."""
    try:
        return stmt.column_descriptions[0]["entity"].__name__
    except Exception:
        return ""


class _FakeSession:
    """AsyncSession 최소 stub.

    - scalar: 엔티티별로 준비된 큐에서 FIFO 반환
    - add:    그대로 누적
    - flush:  PK 미할당 NewsArticle에 fake id를 채워 _tag_article가 깨지지 않게
    """

    def __init__(
        self,
        *,
        article_results: list[Any] | None = None,
        tag_results: list[Any] | None = None,
    ) -> None:
        self._article_q = list(article_results or [])
        self._tag_q = list(tag_results or [])
        self.added: list[Any] = []
        self.flush_count = 0
        self.scalar_calls: list[str] = []
        self._next_pk = 1

    async def scalar(self, stmt: Any) -> Any:
        name = _entity_name(stmt)
        self.scalar_calls.append(name)
        if name == "NewsArticle":
            return self._article_q.pop(0) if self._article_q else None
        if name == "ArticleKeyword":
            return self._tag_q.pop(0) if self._tag_q else None
        return None

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_count += 1
        for obj in self.added:
            if isinstance(obj, NewsArticle) and obj.id is None:
                obj.id = self._next_pk
                self._next_pk += 1


def _make_master() -> MasterKeyword:
    mk = MasterKeyword(keyword="NVIDIA", language="en")
    mk.id = 101
    return mk


def _make_raw(url: str, *, source: str = "Reuters") -> ArticleRaw:
    return ArticleRaw(
        title="NVIDIA reports record earnings",
        url=url,
        content="raw rss snippet body. " * 10,
        source_name=source,
        source_channel="rss",
        published_at=datetime.now(UTC),
        language="en",
    )


def _fake_extract_factory(
    *,
    body: str | None = None,
    image: str | None = None,
    resolved: str | None = None,
):
    """`content_extractor.extract`을 대체할 awaitable factory."""

    async def _extract(_url: str) -> tuple[str | None, str | None, str | None]:
        return (body, image, resolved)

    return _extract


# ---------------------------------------------------------------------------
# 1차 dedup
# ---------------------------------------------------------------------------


async def test_first_stage_dedup_skips_when_canonical_url_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1차 dedup hit: 같은 canonical이 이미 있으면 extract 호출 없이 skip."""
    service = ContentService()
    existing = NewsArticle(
        canonical_url=pu.canonicalize_url("https://publisher.com/article/1"),
        original_url="https://publisher.com/article/1",
        title_original="already saved",
        language="en",
    )
    existing.id = 7

    session = _FakeSession(article_results=[existing], tag_results=[None])

    async def _no_extract(_url: str) -> tuple[None, None, None]:
        raise AssertionError("extract must not be called on 1st-stage dup")

    monkeypatch.setattr(
        "features.content.service.content_extractor.extract", _no_extract
    )

    # utm 추적 파라미터만 다른 URL → canonical은 동일 → 1차에서 잡힘
    saved, dups = await service._persist_articles(
        session,  # type: ignore[arg-type]
        [_make_raw("https://publisher.com/article/1?utm_source=twitter")],
        master_keyword=_make_master(),
    )

    assert (saved, dups) == (0, 1)
    # 새 NewsArticle은 add되지 않음 — tag만 추가
    assert not any(isinstance(o, NewsArticle) for o in session.added)
    tags = [o for o in session.added if isinstance(o, ArticleKeyword)]
    assert len(tags) == 1
    assert tags[0].article_id == 7
    assert tags[0].master_keyword_id == 101


# ---------------------------------------------------------------------------
# 2차 dedup
# ---------------------------------------------------------------------------


async def test_second_stage_dedup_skips_when_resolved_url_matches_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2차 dedup hit: 1차는 miss지만 resolved_url canonical이 publisher article과
    일치하면 +dup, NewsArticle add 없음 — Google News redirect 중복 시나리오."""
    service = ContentService()
    publisher_url = "https://publisher.com/news/abc"
    existing = NewsArticle(
        canonical_url=pu.canonicalize_url(publisher_url),
        original_url=publisher_url,
        title_original="already saved via different URL",
        language="en",
    )
    existing.id = 11

    # 1차: None (Google News URL은 처음 보임)
    # 2차: existing 매칭 (같은 publisher 기사가 이미 DB에 있음)
    session = _FakeSession(article_results=[None, existing], tag_results=[None])

    monkeypatch.setattr(
        "features.content.service.content_extractor.extract",
        _fake_extract_factory(body="x" * 600, resolved=publisher_url),
    )

    saved, dups = await service._persist_articles(
        session,  # type: ignore[arg-type]
        [_make_raw("https://news.google.com/articles/CAIabc?oc=5")],
        master_keyword=_make_master(),
    )

    assert (saved, dups) == (0, 1)
    assert not any(isinstance(o, NewsArticle) for o in session.added)
    # NewsArticle 쿼리는 정확히 2번 (1차 + 2차) 호출됨
    assert session.scalar_calls.count("NewsArticle") == 2
    # tag는 기존 publisher article(id=11)에 새 master_keyword 매핑 추가
    tags = [o for o in session.added if isinstance(o, ArticleKeyword)]
    assert len(tags) == 1
    assert tags[0].article_id == 11
    assert tags[0].master_keyword_id == 101


# ---------------------------------------------------------------------------
# 신규 저장 — canonical_url 전환
# ---------------------------------------------------------------------------


async def test_new_article_stores_publisher_canonical_when_resolved_url_differs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """resolved_url이 raw.url과 다르고 미저장 publisher라면 canonical_url을
    publisher 값으로 저장 — 다음 tick에서 또 다른 redirect URL이 와도
    1차 dedup이 한 번에 잡도록 (fetch 절약)."""
    service = ContentService()
    publisher_url = "https://publisher.com/path/article-42?utm_source=newsletter"
    expected_canonical = pu.canonicalize_url(publisher_url)

    session = _FakeSession(article_results=[None, None], tag_results=[None])

    monkeypatch.setattr(
        "features.content.service.content_extractor.extract",
        _fake_extract_factory(
            body="real long extracted body paragraph. " * 50,
            image="https://publisher.com/og.png",
            resolved=publisher_url,
        ),
    )

    saved, dups = await service._persist_articles(
        session,  # type: ignore[arg-type]
        [_make_raw("https://news.google.com/articles/CAI42?oc=5")],
        master_keyword=_make_master(),
    )

    assert (saved, dups) == (1, 0)
    articles = [o for o in session.added if isinstance(o, NewsArticle)]
    assert len(articles) == 1
    article = articles[0]

    # original_url은 raw URL 보존, canonical_url은 publisher 값
    assert article.original_url == "https://news.google.com/articles/CAI42?oc=5"
    assert article.canonical_url == expected_canonical
    # extract 결과가 raw fallback보다 우선
    assert article.image_url == "https://publisher.com/og.png"
    assert article.content is not None
    assert article.content.startswith("real long extracted body paragraph.")

    # tag는 새 article(flush가 id=1 부여)에 master 매핑
    tags = [o for o in session.added if isinstance(o, ArticleKeyword)]
    assert len(tags) == 1
    assert tags[0].article_id == article.id
    assert session.flush_count == 1


async def test_new_article_skips_second_dedup_when_resolved_url_equals_raw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """resolved_url == raw.url 이면 publisher canonical 재계산이 필요 없으므로
    2차 dedup 쿼리는 생략."""
    service = ContentService()
    url = "https://publisher.com/article-x"

    session = _FakeSession(article_results=[None], tag_results=[None])

    monkeypatch.setattr(
        "features.content.service.content_extractor.extract",
        _fake_extract_factory(body="b" * 600, resolved=url),
    )

    saved, dups = await service._persist_articles(
        session,  # type: ignore[arg-type]
        [_make_raw(url)],
        master_keyword=_make_master(),
    )

    assert (saved, dups) == (1, 0)
    # NewsArticle 쿼리는 1차 한 번만
    assert session.scalar_calls.count("NewsArticle") == 1


# ---------------------------------------------------------------------------
# 추출 실패 fallback
# ---------------------------------------------------------------------------


async def test_extract_failure_falls_back_to_raw_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """추출 실패((None,None,None) 반환) 시 raw.content로 저장, 2차 dedup 생략."""
    service = ContentService()
    raw = _make_raw("https://publisher.com/extract-fail")

    session = _FakeSession(article_results=[None], tag_results=[None])

    monkeypatch.setattr(
        "features.content.service.content_extractor.extract",
        _fake_extract_factory(body=None, image=None, resolved=None),
    )

    saved, dups = await service._persist_articles(
        session,  # type: ignore[arg-type]
        [raw],
        master_keyword=_make_master(),
    )

    assert (saved, dups) == (1, 0)
    article = next(o for o in session.added if isinstance(o, NewsArticle))
    # extract 실패 → raw.content 그대로 사용
    assert article.content == raw.content
    # resolved_url이 None이므로 2차 dedup 쿼리 없음
    assert session.scalar_calls.count("NewsArticle") == 1


# ---------------------------------------------------------------------------
# Tag dedup
# ---------------------------------------------------------------------------


async def test_duplicate_does_not_double_tag_existing_master_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1차 dedup hit + ArticleKeyword 매핑도 이미 있으면 ArticleKeyword INSERT 생략."""
    service = ContentService()
    existing_article = NewsArticle(
        canonical_url=pu.canonicalize_url("https://publisher.com/seen"),
        original_url="https://publisher.com/seen",
        title_original="dup",
        language="en",
    )
    existing_article.id = 55
    existing_tag = ArticleKeyword(article_id=55, master_keyword_id=101)

    session = _FakeSession(
        article_results=[existing_article],
        tag_results=[existing_tag],
    )
    monkeypatch.setattr(
        "features.content.service.content_extractor.extract",
        _fake_extract_factory(),
    )

    saved, dups = await service._persist_articles(
        session,  # type: ignore[arg-type]
        [_make_raw("https://publisher.com/seen")],
        master_keyword=_make_master(),
    )

    assert (saved, dups) == (0, 1)
    # 새 ArticleKeyword는 add되지 않음
    assert not any(isinstance(o, ArticleKeyword) for o in session.added)


# ---------------------------------------------------------------------------
# 다중 raw — 누적 saved/dup 카운트
# ---------------------------------------------------------------------------


async def test_mixed_batch_aggregates_saved_and_dup_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """여러 raw가 섞인 입력에서 saved/dup 카운트가 정확히 누적되는지."""
    service = ContentService()
    existing = NewsArticle(
        canonical_url=pu.canonicalize_url("https://publisher.com/dup-1"),
        original_url="https://publisher.com/dup-1",
        title_original="dup",
        language="en",
    )
    existing.id = 9

    # 첫 raw: 1차 dedup hit → dup +1
    # 둘째 raw: 1차 miss → 신규 저장 → saved +1
    session = _FakeSession(
        article_results=[existing, None],
        tag_results=[None, None],
    )

    monkeypatch.setattr(
        "features.content.service.content_extractor.extract",
        _fake_extract_factory(
            body="extracted long body paragraph. " * 50,
            resolved="https://publisher.com/new-2",
        ),
    )

    raws = [
        _make_raw("https://publisher.com/dup-1"),
        _make_raw("https://publisher.com/new-2"),
    ]
    saved, dups = await service._persist_articles(
        session,  # type: ignore[arg-type]
        raws,
        master_keyword=_make_master(),
    )

    assert (saved, dups) == (1, 1)
    articles = [o for o in session.added if isinstance(o, NewsArticle)]
    assert len(articles) == 1
    tags = [o for o in session.added if isinstance(o, ArticleKeyword)]
    # 두 raw 모두 master_keyword 매핑 추가됨 (한 건은 기존 article에, 한 건은 신규)
    assert len(tags) == 2
