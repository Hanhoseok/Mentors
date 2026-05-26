import importlib

debate_router = importlib.import_module("features.debate.router")
debate_topic_resolver = importlib.import_module("features.debate.topic_resolver")
market_data_models = importlib.import_module("core.market_data.models")
market_data_repository = importlib.import_module("core.market_data.repository")


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
