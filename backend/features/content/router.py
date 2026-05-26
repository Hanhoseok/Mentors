"""콘텐츠 동 라우터 — PR-2 범위: 사용자 관심 키워드 CRUD.

prefix: /api/content
인증: Mentors auth — Depends(get_current_user)

뉴스 피드 (`/news`, `/news/search`)와 스크랩 (`/scraps`)은 PR-3/PR-4에서 추가.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.auth.models import User
from core.db import get_db
from core.exceptions import ConflictError, NotFoundError

from .keyword_service import add_user_keyword, list_user_keywords, remove_user_keyword
from .schemas import (
    UserKeywordCreateRequest,
    UserKeywordListResponse,
    UserKeywordResponse,
)

logger = logging.getLogger("content.router")
router = APIRouter(prefix="/api/content", tags=["content"])


# ---------------------------------------------------------------------------
# 사용자 관심 키워드 CRUD
# user_id는 항상 get_current_user.id에서 가져온다 — 요청 본문에서 받지 않음.
# ---------------------------------------------------------------------------


@router.get("/keywords", response_model=UserKeywordListResponse)
async def list_my_keywords(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserKeywordListResponse:
    """현재 로그인 사용자의 관심 키워드 목록."""
    rows = await list_user_keywords(db, user_id=user.id)
    items = [UserKeywordResponse.model_validate(r) for r in rows]
    return UserKeywordListResponse(items=items, total=len(items))


@router.post("/keywords", response_model=UserKeywordResponse, status_code=201)
async def add_my_keyword(
    payload: UserKeywordCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserKeywordResponse:
    """사용자 관심 키워드 추가. 중복은 ConflictError."""
    user_keyword = await add_user_keyword(
        db,
        user_id=user.id,
        keyword=payload.keyword,
        language=payload.language,
        source="manual",
    )
    if user_keyword is None:
        raise ConflictError("이미 등록된 키워드입니다")
    logger.info(
        "content.user_keyword_added",
        extra={"user_id": user.id, "keyword_id": user_keyword.id},
    )
    return UserKeywordResponse.model_validate(user_keyword)


@router.delete("/keywords/{user_keyword_id}", status_code=204)
async def remove_my_keyword(
    user_keyword_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """사용자 관심 키워드 삭제. 본인 소유만 가능."""
    deleted = await remove_user_keyword(db, user_id=user.id, user_keyword_id=user_keyword_id)
    if not deleted:
        raise NotFoundError("키워드를 찾을 수 없습니다")


__all__ = ["router"]
