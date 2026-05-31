"""사용자별 관심 키워드 영속화 — router와 onboarding 핸들러가 공유.

- 라우터는 user_id를 항상 get_current_user.id에서 받음 (request body 금지)
- 핸들러(handlers.on_onboarding_completed)는 event.user_id로 호출
- MasterKeyword는 글로벌 풀 — get_or_create 패턴으로 신규 키워드 시 자동 추가
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import MasterKeyword, UserKeyword

logger = logging.getLogger("content.keyword_service")


async def list_user_keywords(db: AsyncSession, *, user_id: int) -> Sequence[UserKeyword]:
    """사용자의 모든 관심 키워드. master_keyword를 eager load."""
    stmt = (
        select(UserKeyword)
        .where(UserKeyword.user_id == user_id)
        .options(selectinload(UserKeyword.master_keyword))
        .order_by(desc(UserKeyword.created_at))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_or_create_master_keyword(
    db: AsyncSession,
    *,
    keyword: str,
    language: str = "auto",
    source: str = "manual",
) -> MasterKeyword:
    """글로벌 키워드 풀에 키워드 추가(또는 기존 행 반환).

    `keyword`는 unique. 동시 호출 충돌 시 IntegrityError를 잡고 재조회.
    """
    normalized = keyword.strip()
    # db.scalar()는 Any를 반환해서 mypy strict가 narrowing 못 함 — 명시적 annotation.
    existing: MasterKeyword | None = await db.scalar(
        select(MasterKeyword).where(MasterKeyword.keyword == normalized)
    )
    if existing is not None:
        return existing

    new = MasterKeyword(
        keyword=normalized,
        language=language,
        source=source,
        priority="P2",
        is_active=True,
    )
    db.add(new)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(MasterKeyword).where(MasterKeyword.keyword == normalized)
        )
        if existing is None:
            raise
        return existing
    return new


async def add_user_keyword(
    db: AsyncSession,
    *,
    user_id: int,
    keyword: str,
    language: str = "auto",
    source: str = "manual",
    weight: int = 1,
) -> UserKeyword | None:
    """사용자에게 키워드 연결. 이미 있으면 None 반환 (호출자가 Conflict 처리)."""
    master = await get_or_create_master_keyword(
        db, keyword=keyword, language=language, source=source
    )

    existing = await db.scalar(
        select(UserKeyword).where(
            UserKeyword.user_id == user_id,
            UserKeyword.master_keyword_id == master.id,
        )
    )
    if existing is not None:
        return None

    user_keyword = UserKeyword(
        user_id=user_id,
        master_keyword_id=master.id,
        source=source,
        weight=weight,
    )
    db.add(user_keyword)
    await db.commit()
    await db.refresh(user_keyword, attribute_names=["master_keyword"])
    return user_keyword


async def remove_user_keyword(
    db: AsyncSession,
    *,
    user_id: int,
    user_keyword_id: int,
) -> bool:
    """본인 소유 키워드만 삭제 가능. 삭제 성공 시 True."""
    user_keyword = await db.scalar(
        select(UserKeyword).where(
            UserKeyword.id == user_keyword_id,
            UserKeyword.user_id == user_id,
        )
    )
    if user_keyword is None:
        return False
    await db.delete(user_keyword)
    await db.commit()
    return True


async def seed_keywords_from_interests(
    db: AsyncSession,
    *,
    user_id: int,
    interests: Sequence[str],
) -> int:
    """온보딩 interest 태그 리스트를 사용자 키워드로 시딩 (멱등).

    각 interest 태그마다:
      1. 해당 태그를 MasterKeyword로 get-or-create (source='onboarding')
      2. UserKeyword 행 추가 (이미 있으면 skip)
    추가로 등록된 행 수를 반환. 모두 이미 등록되어 있으면 0.
    """
    added = 0
    for raw in interests:
        tag = raw.strip()
        if not tag:
            continue
        try:
            user_keyword = await add_user_keyword(
                db,
                user_id=user_id,
                keyword=tag,
                language="auto",
                source="onboarding",
            )
        except Exception:
            logger.exception(
                "content.seed_keyword_failed",
                extra={"user_id": user_id, "keyword": tag},
            )
            continue
        if user_keyword is not None:
            added += 1
    return added


__all__ = [
    "add_user_keyword",
    "get_or_create_master_keyword",
    "list_user_keywords",
    "remove_user_keyword",
    "seed_keywords_from_interests",
]
