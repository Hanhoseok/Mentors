from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class MarketEntity(Base):
    __tablename__ = "market_entities"
    __table_args__ = (
        UniqueConstraint("kind", "symbol", name="uq_market_entities_kind_symbol"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(120), index=True)
    exchange: Mapped[str | None] = mapped_column(String(40))
    sector: Mapped[str | None] = mapped_column(String(80), index=True)
    industry: Mapped[str | None] = mapped_column(String(120))
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    themes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    source: Mapped[str] = mapped_column(String(80), nullable=False, server_default="manual")
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    news_items: Mapped[list[MarketNewsItem]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
    )


class MarketNewsItem(Base):
    __tablename__ = "market_news_items"
    __table_args__ = (
        UniqueConstraint("entity_id", "url", name="uq_market_news_items_entity_url"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("market_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity: Mapped[MarketEntity] = relationship(back_populates="news_items")
