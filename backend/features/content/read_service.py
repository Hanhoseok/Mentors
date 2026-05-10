"""ContentReader 구현 (§4.16, ADR-014).

다른 동(일일리포트 등)이 `from core.read_services import content_reader`로 호출.
"""

from core.contracts import NewsId, UserId
from core.read_services import NewsRef


class ContentReadServiceImpl:
    async def get_today_news_for_user(self, user_id: UserId, top_k: int = 5) -> list[NewsRef]:
        # TODO: news 테이블에서 사용자의 학습 멘토 전략 기준으로 필터링
        # - user_context.get_for_mentor_chat(user_id).selected_mentor_id 활용
        # - news 테이블 쿼리 (콘텐츠 동 자체 테이블 — 미구현)
        return []

    async def get_news_by_id(self, news_id: NewsId) -> NewsRef | None:
        # TODO: news 테이블에서 단건 조회
        return None
