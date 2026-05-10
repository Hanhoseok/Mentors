"""5동 — 콘텐츠 (뉴스·시장지표·스크랩·discovery).

owner: TODO
관련 FR: FR-05, FR-06, FR-08, UC-05, UC-06, UC-08
외부 API: ECOS, yFinance, Naver News, Tavily (콘텐츠 동 자체 — 코어 래퍼 불필요)
"""

from fastapi import APIRouter, Depends

from core.auth.dependencies import get_current_user
from core.auth.models import User

router = APIRouter(prefix="/api/content", tags=["content"])


@router.get("/news/today")
async def today_news(user: User = Depends(get_current_user)) -> dict[str, list[dict[str, str]]]:
    # TODO: news 테이블 + 멘토 전략 필터링
    return {"news": []}
