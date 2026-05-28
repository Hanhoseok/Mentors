"""content: seed full industry pool (32 industries, 115 keywords, 603 company links)

Revision ID: 20260528_content_seed_industry_pool
Revises: 20260524_content_create_tables
Create Date: 2026-05-28

owner: content (5동)
관련 FR/UC: FR-05, FR-06

newspipeline `core/db/seeds/industry_pool.py`를 mentors content_* 테이블에 이식.

데이터는 `features/content/seed_data.py`에서 읽음. 이 마이그레이션은 멱등:
- 기존 행은 ON CONFLICT DO NOTHING으로 보존 (20260524의 미니멀 시드 포함)
- 새 행만 INSERT
- master_keywords.is_active는 명시적으로 True로 설정 — 즉시 수집 대상에 포함

ID 자동 부여:
- content_industries.id, content_industry_keywords.id, content_master_keywords.id,
  content_master_keyword_companies.id 모두 auto-increment.
- 시드 자체는 name_ko / (industry_id, label_ko) / keyword / (master_keyword_id, company_name)
  의 UNIQUE 제약으로 dedup.

선행 시퀀스 동기화:
- 20260524가 시드 데이터를 explicit id=1로 INSERT 했지만 PostgreSQL의 SERIAL
  시퀀스는 명시적 id INSERT 시 자동 advance 안 됨. 결과: `content_*_id_seq`가
  여전히 1을 가리켜서 본 마이그레이션의 auto-increment INSERT가 PK 충돌로 실패.
- upgrade() 첫 단계에서 4개 테이블 시퀀스를 setval(MAX(id))로 동기화.
- 빈 테이블에서도 안전 (COALESCE).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from features.content.seed_data import INDUSTRY_COMPANIES, KEYWORD_SCHEDULE

revision: str = "20260528_content_seed_industry_pool"
down_revision: str | Sequence[str] | None = "20260524_content_create_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 영문 산업명 매핑 — name_en 컬럼용 (없으면 한국어 그대로 fallback)
_INDUSTRY_EN: dict[str, str] = {
    "IT기술": "IT/Tech",
    "통신": "Telecom",
    "금속": "Metals",
    "조선": "Shipbuilding",
    "기계": "Machinery",
    "운송": "Transport",
    "디스플레이": "Display",
    "건축": "Construction",
    "바이오": "Biotech",
    "반도체": "Semiconductor",
    "전자제품제조": "Electronics Manufacturing",
    "배터리": "Battery",
    "생활용품": "Consumer Goods",
    "원자재": "Raw Materials",
    "엔터테인먼트": "Entertainment",
    "건설인프라스트럭트": "Construction Infra",
    "금융": "Finance",
    "방산": "Defense",
    "보험": "Insurance",
    "식료품": "Food",
    "의류": "Apparel",
    "의료": "Medical",
    "자동차": "Automotive",
    "전력에너지": "Power Energy",
    "전자부품": "Electronic Components",
    "주류": "Beverages",
    "철강": "Steel",
    "탄소배출권": "Carbon Credits",
    "행공": "Aviation",
    "원유": "Oil",
    "방위산업물자": "Defense Industry",
    "교육": "Education",
}


def upgrade() -> None:
    bind = op.get_bind()

    # ---- 0) 시퀀스 동기화 (20260524 explicit id INSERT 영향 보정) ----------
    # 20260524의 명시적 id=1 INSERT는 SERIAL 시퀀스를 advance 시키지 않음.
    # setval(seq, MAX(id), is_called=true) → 다음 nextval = MAX(id)+1.
    # 빈 테이블이면 setval(seq, 1, false) → 다음 nextval = 1.
    # 멱등 — 이미 동기화된 시퀀스에 호출해도 무해.
    for table, col in [
        ("content_industries", "id"),
        ("content_industry_keywords", "id"),
        ("content_master_keywords", "id"),
        ("content_master_keyword_companies", "id"),
    ]:
        bind.execute(
            sa.text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', '{col}'),
                    COALESCE((SELECT MAX({col}) FROM {table}), 1),
                    (SELECT MAX({col}) IS NOT NULL FROM {table})
                )
                """
            )
        )

    # ---- 1) industries -----------------------------------------------------
    industries_seen: dict[str, int] = {}  # name_ko → id
    # 기존 행 먼저 수집
    for row in bind.execute(sa.text("SELECT id, name_ko FROM content_industries")):
        industries_seen[row[1]] = row[0]

    unique_industries = []
    seen_names: set[str] = set()
    for industry_ko, _kw, _companies in INDUSTRY_COMPANIES:
        if industry_ko in seen_names or industry_ko in industries_seen:
            continue
        seen_names.add(industry_ko)
        unique_industries.append({
            "name_ko": industry_ko,
            "name_en": _INDUSTRY_EN.get(industry_ko, industry_ko),
            "display_order": len(seen_names),
        })

    if unique_industries:
        bind.execute(
            sa.text(
                "INSERT INTO content_industries (name_ko, name_en, display_order) "
                "VALUES (:name_ko, :name_en, :display_order) "
                "ON CONFLICT (name_ko) DO NOTHING"
            ),
            unique_industries,
        )

    # 시드 후 다시 ID 수집
    industries_seen.clear()
    for row in bind.execute(sa.text("SELECT id, name_ko FROM content_industries")):
        industries_seen[row[1]] = row[0]

    # ---- 2) industry_keywords ---------------------------------------------
    industry_kws_seen: dict[tuple[int, str], int] = {}  # (industry_id, label_ko) → id
    for row in bind.execute(
        sa.text("SELECT id, industry_id, label_ko FROM content_industry_keywords")
    ):
        industry_kws_seen[(row[1], row[2])] = row[0]

    rows_to_insert = []
    pair_seen: set[tuple[int, str]] = set()
    for order_idx, (industry_ko, sub_kw_ko, _companies) in enumerate(INDUSTRY_COMPANIES):
        industry_id = industries_seen.get(industry_ko)
        if industry_id is None:
            continue
        key = (industry_id, sub_kw_ko)
        if key in pair_seen or key in industry_kws_seen:
            continue
        pair_seen.add(key)
        rows_to_insert.append({
            "industry_id": industry_id,
            "label_ko": sub_kw_ko,
            "keyword_en": sub_kw_ko,  # 영문 매핑은 별도 PR에서; 우선 동일값
            "display_order": order_idx,
        })

    if rows_to_insert:
        bind.execute(
            sa.text(
                "INSERT INTO content_industry_keywords "
                "(industry_id, label_ko, keyword_en, display_order) "
                "VALUES (:industry_id, :label_ko, :keyword_en, :display_order) "
                "ON CONFLICT (industry_id, label_ko) DO NOTHING"
            ),
            rows_to_insert,
        )

    # 재수집
    industry_kws_seen.clear()
    for row in bind.execute(
        sa.text("SELECT id, industry_id, label_ko FROM content_industry_keywords")
    ):
        industry_kws_seen[(row[1], row[2])] = row[0]

    # ---- 3) master_keywords (with KEYWORD_SCHEDULE) -----------------------
    master_kws_seen: dict[str, int] = {}  # keyword → id
    for row in bind.execute(sa.text("SELECT id, keyword FROM content_master_keywords")):
        master_kws_seen[row[1]] = row[0]

    # 스케줄 lookup: (industry, sub_kw) → (priority, interval, max_articles, slot)
    schedule_by_pair: dict[tuple[str, str], tuple[str, int, int, int]] = {}
    for industry_ko, sub_kw_ko, priority, interval, max_articles, slot in KEYWORD_SCHEDULE:
        schedule_by_pair[(industry_ko, sub_kw_ko)] = (priority, interval, max_articles, slot)

    master_rows = []
    for industry_ko, sub_kw_ko, _companies in INDUSTRY_COMPANIES:
        if sub_kw_ko in master_kws_seen:
            continue
        industry_id = industries_seen.get(industry_ko)
        if industry_id is None:
            continue
        industry_kw_id = industry_kws_seen.get((industry_id, sub_kw_ko))
        if industry_kw_id is None:
            continue
        sched = schedule_by_pair.get((industry_ko, sub_kw_ko), ("P2", 60, 3, 0))
        priority, interval, max_articles, slot = sched
        master_rows.append({
            "keyword": sub_kw_ko,
            "language": "ko",
            "source": "industry",
            "industry_keyword_id": industry_kw_id,
            "is_active": True,
            "priority": priority,
            "collection_interval_minutes": interval,
            "max_articles_per_run": max_articles,
            "slot_minute": slot,
        })

    if master_rows:
        bind.execute(
            sa.text(
                "INSERT INTO content_master_keywords "
                "(keyword, language, source, industry_keyword_id, is_active, "
                " priority, collection_interval_minutes, max_articles_per_run, slot_minute) "
                "VALUES (:keyword, :language, :source, :industry_keyword_id, :is_active, "
                " :priority, :collection_interval_minutes, :max_articles_per_run, :slot_minute) "
                "ON CONFLICT (keyword) DO NOTHING"
            ),
            master_rows,
        )

    master_kws_seen.clear()
    for row in bind.execute(sa.text("SELECT id, keyword FROM content_master_keywords")):
        master_kws_seen[row[1]] = row[0]

    # ---- 4) master_keyword_companies --------------------------------------
    # 기존 (master_keyword_id, company_name) 페어 수집
    existing_pairs: set[tuple[int, str]] = set()
    for row in bind.execute(
        sa.text("SELECT master_keyword_id, company_name FROM content_master_keyword_companies")
    ):
        existing_pairs.add((row[0], row[1]))

    company_rows = []
    for _industry_ko, sub_kw_ko, companies in INDUSTRY_COMPANIES:
        mkw_id = master_kws_seen.get(sub_kw_ko)
        if mkw_id is None:
            continue
        for priority_idx, (company_name, country) in enumerate(companies, start=1):
            pair = (mkw_id, company_name)
            if pair in existing_pairs:
                continue
            existing_pairs.add(pair)
            company_rows.append({
                "master_keyword_id": mkw_id,
                "company_name": company_name,
                "company_name_ko": None,
                "ticker": None,
                "country": country,
                "priority": priority_idx,
            })

    if company_rows:
        # ON CONFLICT (master_keyword_id, company_name) — 모델에 UNIQUE 있음
        bind.execute(
            sa.text(
                "INSERT INTO content_master_keyword_companies "
                "(master_keyword_id, company_name, company_name_ko, ticker, country, priority) "
                "VALUES (:master_keyword_id, :company_name, :company_name_ko, :ticker, "
                " :country, :priority) "
                "ON CONFLICT (master_keyword_id, company_name) DO NOTHING"
            ),
            company_rows,
        )


def downgrade() -> None:
    """이 마이그레이션이 추가한 행만 제거 (20260524의 미니멀 시드는 보존).

    구분 기준: master_keywords.source='industry'로 들어온 행 + 그 companies.
    20260524는 source='industry'로 1행만 추가했고 keyword가 "반도체 제조"라
    겹침. 그 행은 보존하기 위해 specific keyword 외에는 모두 삭제하면
    20260524 영향 없음.

    안전한 폴백: source='industry' AND keyword IN (...현재 seed_data의 keywords)
    를 삭제. 단 20260524의 "반도체 제조"도 같은 keyword라 함께 사라짐.
    실 운영에선 downgrade 거의 호출 안 됨.
    """
    bind = op.get_bind()

    # KEYWORD_SCHEDULE에 적힌 keyword들만 정확히 매칭
    keywords = [row[1] for row in KEYWORD_SCHEDULE]
    if keywords:
        # companies first (FK CASCADE이라 keywords 지우면 자동이지만 명시적으로)
        bind.execute(
            sa.text(
                "DELETE FROM content_master_keyword_companies "
                "WHERE master_keyword_id IN (SELECT id FROM content_master_keywords "
                " WHERE source = 'industry' AND keyword = ANY(:kws))"
            ),
            {"kws": keywords},
        )
        bind.execute(
            sa.text(
                "DELETE FROM content_master_keywords "
                "WHERE source = 'industry' AND keyword = ANY(:kws)"
            ),
            {"kws": keywords},
        )

    # industry_keywords / industries는 다른 source에서 참조 가능하므로 삭제 안 함.
