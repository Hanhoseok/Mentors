"""market data: add search indexes

Revision ID: 20260604_market_search
Revises: 20260531_merge_heads
Create Date: 2026-06-04

"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260604_market_search"
down_revision: str | Sequence[str] | None = "20260531_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_market_entities_search_vector
        ON market_entities
        USING gin (
            to_tsvector(
                'simple',
                coalesce(symbol, '') || ' ' ||
                coalesce(name, '') || ' ' ||
                coalesce(name_en, '') || ' ' ||
                coalesce(sector, '') || ' ' ||
                coalesce(industry, '')
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_market_entities_aliases_gin
        ON market_entities USING gin (aliases)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_market_entities_themes_gin
        ON market_entities USING gin (themes)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_market_entities_themes_gin")
    op.execute("DROP INDEX IF EXISTS ix_market_entities_aliases_gin")
    op.execute("DROP INDEX IF EXISTS ix_market_entities_search_vector")
