import asyncio
import importlib
from datetime import UTC, datetime

import httpx
import pytest

debate_router = importlib.import_module("features.debate.router")
debate_topic_resolver = importlib.import_module("features.debate.topic_resolver")
market_data_collector = importlib.import_module("core.market_data.collector")
market_data_dart = importlib.import_module("core.market_data.dart")
market_data_finnhub = importlib.import_module("core.market_data.finnhub")
market_data_models = importlib.import_module("core.market_data.models")
market_data_repository = importlib.import_module("core.market_data.repository")
content_read_service = importlib.import_module("features.content.read_service")
read_service_protocols = importlib.import_module("core.read_services.protocols")

_DART_TEST_XML = """
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>삼성전자</corp_name>
    <stock_code>005930</stock_code>
  </list>
</result>
"""


def test_market_data_resolver_treats_unknown_company_as_stock_candidate() -> None:
    entity = market_data_models.MarketEntity(
        kind="stock",
        symbol="PLTR",
        name="팔란티어",
        name_en="Palantir",
        aliases=["palantir", "pltr"],
    )
    match = market_data_repository.MarketEntityMatch(
        entity=entity,
        matched_text="팔란티어",
        score=100,
    )

    resolution = debate_topic_resolver._to_resolution("팔란티어 전망", match)

    assert resolution.topic_type == "stock"
    assert resolution.topic == "팔란티어 주식 투자 전망"
    assert debate_router._news_queries(resolution.topic)[0] == "팔란티어"


def test_market_data_resolver_treats_unknown_related_stocks_as_theme() -> None:
    entity = market_data_models.MarketEntity(
        kind="theme",
        symbol="SPACE_TECH",
        name="우주테크",
        aliases=["우주항공", "항공우주"],
    )
    match = market_data_repository.MarketEntityMatch(
        entity=entity,
        matched_text="우주테크",
        score=100,
    )

    resolution = debate_topic_resolver._to_resolution("앞으로 우주테크 관련주의 전망", match)

    assert resolution.topic_type == "theme"
    assert resolution.topic == "우주테크 관련주 전망"
    assert debate_router._news_queries(resolution.topic)[0] == "우주테크 관련주 전망"


def test_market_news_item_unique_constraint_is_scoped_to_entity() -> None:
    constraints = {
        constraint.name: tuple(constraint.columns.keys())
        for constraint in market_data_models.MarketNewsItem.__table__.constraints
    }

    assert constraints["uq_market_news_items_entity_url"] == ("entity_id", "url")
    assert all(columns != ("url",) for columns in constraints.values())


def test_stock_theme_labels_are_not_used_as_primary_match_names() -> None:
    stock = market_data_models.MarketEntity(
        kind="stock",
        symbol="PLTR",
        name="팔란티어",
        name_en="Palantir",
        aliases=["palantir", "pltr"],
        themes=["AI", "방산"],
    )
    theme = market_data_models.MarketEntity(
        kind="theme",
        symbol="AI",
        name="AI",
        aliases=["인공지능"],
        themes=["AI", "AI 반도체"],
    )

    stock_match = market_data_repository._score_entity_match(stock, "AI 전망", ["AI"])
    theme_match = market_data_repository._score_entity_match(theme, "AI 전망", ["AI"])

    assert stock_match is None
    assert theme_match is not None
    assert theme_match.entity.kind == "theme"


def test_topic_discovery_queries_keep_unknown_company_name_first() -> None:
    queries = market_data_collector._topic_discovery_queries("nvidia 전망")

    assert queries[0] == "nvidia"
    assert "전망" not in queries


def test_topic_discovery_queries_strip_korean_particle_from_latin_name() -> None:
    queries = market_data_collector._topic_discovery_queries("openai의 오너리스크")

    assert queries == ["openai"]


def test_topic_discovery_queries_do_not_use_aliases_as_api_search_terms() -> None:
    queries = market_data_collector._topic_discovery_queries("엔비디아 전망")

    assert "NVDA" not in queries
    assert queries == ["엔비디아"]


def test_topic_discovery_queries_skip_broad_theme_tokens() -> None:
    queries = market_data_collector._topic_discovery_queries("AI 전망")

    assert queries == []


def test_content_industry_topic_tokens_expand_common_english_aliases() -> None:
    tokens = content_read_service._topic_tokens("AI 반도체 전망")

    assert "AI" in tokens
    assert "인공지능" in tokens
    assert "반도체" in tokens


def test_discovery_query_scope_routes_by_language() -> None:
    assert market_data_collector._discovery_query_scope("삼성전자") == "korean"
    assert market_data_collector._discovery_query_scope("nvidia") == "global"
    assert market_data_collector._discovery_query_scope("삼성전자005930") == "mixed"


def test_global_stock_korean_aliases_are_matchable_after_cache_seed() -> None:
    entity = market_data_models.MarketEntity(
        kind="stock",
        symbol="NVDA",
        name="NVIDIA Corp",
        name_en="NVIDIA Corp",
        aliases=["NVDA", "NVIDIA Corp", "엔비디아"],
    )

    match = market_data_repository._score_entity_match(entity, "엔비디아 전망", ["엔비디아"])

    assert match is not None
    assert match.entity.symbol == "NVDA"


@pytest.mark.asyncio
async def test_find_entity_match_searches_json_alias_candidates_without_fallback_scan() -> None:
    class EmptyResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(str(statement))
            return EmptyResult()

    db = FakeSession()

    match = await market_data_repository.find_entity_match(db, "엔비디아 전망")

    assert match is None
    assert len(db.statements) == 1
    assert "aliases" in db.statements[0]
    assert "themes" in db.statements[0]


def test_dart_parser_extracts_listed_korean_stock_candidates() -> None:
    payload = """
    <result>
      <list>
        <corp_code>00126380</corp_code>
        <corp_name>삼성전자</corp_name>
        <stock_code>005930</stock_code>
      </list>
      <list>
        <corp_code>00164779</corp_code>
        <corp_name>카카오</corp_name>
        <stock_code>035720</stock_code>
      </list>
      <list>
        <corp_code>00000000</corp_code>
        <corp_name>비상장회사</corp_name>
        <stock_code></stock_code>
      </list>
    </result>
    """

    stocks = market_data_dart._parse_stocks(payload)

    assert stocks[0].code == "005930"
    assert stocks[0].name == "삼성전자"
    assert stocks[0].corp_code == "00126380"
    assert stocks[0].market == "KRX"
    assert stocks[1].code == "035720"


@pytest.mark.asyncio
async def test_dart_client_does_not_cache_failed_download(monkeypatch) -> None:
    client = market_data_dart.DartMarketDataClient()
    calls = 0

    class FakeResponse:
        content = _DART_TEST_XML

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.RequestError("temporary failure")
            return FakeResponse()

    monkeypatch.setattr(market_data_dart.settings, "dart_api_key", "test-key")
    monkeypatch.setattr(market_data_dart.httpx, "AsyncClient", FakeAsyncClient)

    assert await client.search_stocks("삼성전자") == []
    assert client._stocks is None

    stocks = await client.search_stocks("삼성전자")

    assert calls == 2
    assert stocks[0].code == "005930"
    assert client._stocks is not None


@pytest.mark.asyncio
async def test_dart_client_reuses_fresh_cache(monkeypatch) -> None:
    client = market_data_dart.DartMarketDataClient()
    calls = 0

    class FakeResponse:
        content = _DART_TEST_XML

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            return FakeResponse()

    monkeypatch.setattr(market_data_dart.settings, "dart_api_key", "test-key")
    monkeypatch.setattr(market_data_dart.httpx, "AsyncClient", FakeAsyncClient)

    first = await client.search_stocks("삼성전자")
    second = await client.search_stocks("삼성전자")

    assert calls == 1
    assert first == second


@pytest.mark.asyncio
async def test_dart_client_coalesces_concurrent_initial_loads(monkeypatch) -> None:
    client = market_data_dart.DartMarketDataClient()
    calls = 0

    class FakeResponse:
        content = _DART_TEST_XML

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            return FakeResponse()

    monkeypatch.setattr(market_data_dart.settings, "dart_api_key", "test-key")
    monkeypatch.setattr(market_data_dart.httpx, "AsyncClient", FakeAsyncClient)

    results = await asyncio.gather(
        client.search_stocks("삼성전자"),
        client.search_stocks("삼성전자"),
        client.search_stocks("삼성전자"),
    )

    assert calls == 1
    assert all(result[0].code == "005930" for result in results)


@pytest.mark.asyncio
async def test_discover_entity_from_topic_upserts_external_stock(monkeypatch) -> None:
    upsert_calls = []

    class FakeFinnhubClient:
        async def search_companies(self, query: str, *, limit: int = 5):
            assert query == "nvidia"
            return [
                market_data_finnhub.FinnhubCompany(
                    symbol="NVDA",
                    display_symbol="NVDA",
                    description="NVIDIA Corp",
                    kind="Common Stock",
                )
            ]

        async def get_company_profile(self, symbol: str):
            assert symbol == "NVDA"
            return market_data_finnhub.FinnhubCompanyProfile(
                symbol="NVDA",
                name="NVIDIA Corp",
                exchange="NASDAQ",
                industry="Semiconductors",
                country="US",
            )

        async def get_company_news(self, symbol: str, *, limit: int = 5):
            return []

    async def fake_upsert_entity(db, **kwargs):
        upsert_calls.append(kwargs)
        return market_data_models.MarketEntity(
            kind=kwargs["kind"],
            symbol=kwargs["symbol"],
            name=kwargs["name"],
            name_en=kwargs["name_en"],
            exchange=kwargs.get("exchange"),
            industry=kwargs["industry"],
            aliases=kwargs["aliases"],
            themes=kwargs["themes"],
            source=kwargs["source"],
            confidence=kwargs["confidence"],
        )

    monkeypatch.setattr(market_data_collector, "upsert_entity", fake_upsert_entity)
    monkeypatch.setattr(market_data_collector.settings, "market_data_discovery_enabled", True)

    entity = await market_data_collector.discover_entity_from_topic(
        object(),
        "nvidia 전망",
        client=FakeFinnhubClient(),
    )

    assert entity is not None
    assert entity.kind == "stock"
    assert entity.symbol == "NVDA"
    assert entity.source == "finnhub"
    assert "NVIDIA Corp" in entity.aliases
    assert "엔비디아" in entity.aliases
    assert "Semiconductors" in entity.themes
    assert any(
        call["kind"] == "theme"
        and call["symbol"] == "INDUSTRY_SEMICONDUCTORS"
        and call["source"] == "finnhub_profile"
        for call in upsert_calls
    )


@pytest.mark.asyncio
async def test_discover_entity_from_topic_uses_korean_stock_search_first(monkeypatch) -> None:
    class FakeKoreanClient:
        async def search_stocks(self, query: str, *, limit: int = 5):
            assert query == "삼성전자"
            return [
                market_data_dart.DartStock(
                    code="005930",
                    name="삼성전자",
                    corp_code="00126380",
                )
            ]

    class FakeFinnhubClient:
        async def search_companies(self, query: str, *, limit: int = 5):
            raise AssertionError("Finnhub should not be called when Korean search matches")

        async def get_company_profile(self, symbol: str):
            raise AssertionError("Finnhub should not be called when Korean search matches")

        async def get_company_news(self, symbol: str, *, limit: int = 5):
            raise AssertionError("Finnhub should not be called when Korean search matches")

    async def fake_upsert_entity(db, **kwargs):
        return market_data_models.MarketEntity(
            kind=kwargs["kind"],
            symbol=kwargs["symbol"],
            name=kwargs["name"],
            name_en=kwargs["name_en"],
            exchange=kwargs.get("exchange"),
            sector=kwargs.get("sector"),
            aliases=kwargs["aliases"],
            themes=kwargs["themes"],
            source=kwargs["source"],
            confidence=kwargs["confidence"],
        )

    monkeypatch.setattr(market_data_collector, "upsert_entity", fake_upsert_entity)
    monkeypatch.setattr(market_data_collector.settings, "market_data_discovery_enabled", True)

    entity = await market_data_collector.discover_entity_from_topic(
        object(),
        "삼성전자 전망",
        client=FakeFinnhubClient(),
        korean_client=FakeKoreanClient(),
    )

    assert entity is not None
    assert entity.kind == "stock"
    assert entity.symbol == "005930"
    assert entity.name == "삼성전자"
    assert entity.exchange == "KRX"
    assert entity.source == "dart"


@pytest.mark.asyncio
async def test_discover_entity_from_topic_falls_back_to_content_industry_topic(
    monkeypatch,
) -> None:
    class FakeFinnhubClient:
        async def search_companies(self, query: str, *, limit: int = 5):
            return []

        async def get_company_profile(self, symbol: str):
            return None

        async def get_company_news(self, symbol: str, *, limit: int = 5):
            return []

    class FakeKoreanClient:
        async def search_stocks(self, query: str, *, limit: int = 5):
            return []

    class FakeContentReader:
        async def find_industry_topic(self, topic: str):
            assert topic == "양자컴퓨터 산업 전망"
            return read_service_protocols.IndustryTopicRef(
                industry="IT기술",
                keyword="양자컴퓨터",
                aliases=["IT기술", "양자컴퓨터", "quantum computing"],
                companies=["IonQ", "NVIDIA"],
            )

    async def fake_upsert_entity(db, **kwargs):
        return market_data_models.MarketEntity(
            kind=kwargs["kind"],
            symbol=kwargs["symbol"],
            name=kwargs["name"],
            name_en=kwargs["name_en"],
            sector=kwargs.get("sector"),
            industry=kwargs.get("industry"),
            aliases=kwargs["aliases"],
            themes=kwargs["themes"],
            source=kwargs["source"],
            confidence=kwargs["confidence"],
        )

    monkeypatch.setattr(market_data_collector, "upsert_entity", fake_upsert_entity)
    monkeypatch.setattr(market_data_collector, "content_reader", FakeContentReader())
    monkeypatch.setattr(market_data_collector.settings, "market_data_discovery_enabled", True)

    entity = await market_data_collector.discover_entity_from_topic(
        object(),
        "양자컴퓨터 산업 전망",
        client=FakeFinnhubClient(),
        korean_client=FakeKoreanClient(),
    )

    assert entity is not None
    assert entity.kind == "theme"
    assert entity.name == "양자컴퓨터"
    assert entity.industry == "IT기술"
    assert entity.source == "content_pipeline"
    assert "IonQ" in entity.themes


@pytest.mark.asyncio
async def test_debate_uses_content_pipeline_news_before_external_news(monkeypatch) -> None:
    class FakeContentReader:
        async def search_news_for_topic(self, topic: str, keywords: list[str], top_k: int = 5):
            assert topic == "양자컴퓨터 관련주 전망"
            assert "양자컴퓨터" in keywords
            return [
                read_service_protocols.NewsRef(
                    id=1,
                    title="양자컴퓨터 관련주 정책 수혜",
                    url="https://example.com/news/1",
                    published_at=datetime(2026, 6, 1, tzinfo=UTC),
                    source="content-pipeline",
                    summary="양자컴퓨터 투자와 반도체 수요 기대가 함께 부각되고 있다",
                    keywords=["양자컴퓨터", "반도체"],
                )
            ]

    async def fail_external_news(query: str, top_k: int = 3):
        raise AssertionError("external news search should not run when content news is enough")

    monkeypatch.setattr(debate_router, "content_reader", FakeContentReader())
    monkeypatch.setattr(debate_router.news_search, "search", fail_external_news)

    docs = await debate_router._search_content_news_documents("양자컴퓨터 관련주 전망")

    assert docs[0].id == "content_news_1"
    assert docs[0].metadata["source"] == "content-pipeline"
    assert "양자컴퓨터 투자" in docs[0].text
