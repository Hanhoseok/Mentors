from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://mentors:mentors@localhost:5432/mentors")
os.environ.setdefault("JWT_SECRET", "dev-smoke-secret-change-me")
os.environ.setdefault("GOOGLE_CLIENT_ID", "dev-smoke")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "dev-smoke")

from core.ai_pipeline import RAGContext
from core.contracts import Tier
from core.exceptions import ExternalServiceError
from features.debate.models import DebateMessage, DebateSession

debate_router = importlib.import_module("features.debate.router")
debate_service = importlib.import_module("features.debate.service")

DEFAULT_TOPIC = "금리 상승기 성장주 전략"


class FakeStartDB:
    def __init__(self) -> None:
        self.session: DebateSession | None = None

    def add(self, obj: DebateSession) -> None:
        self.session = obj
        obj.id = 123
        obj.status = obj.status or "created"

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: DebateSession) -> None:
        pass


class FakeStreamDB:
    def __init__(self, session: DebateSession) -> None:
        self.session = session
        self.messages: list[DebateMessage] = []

    async def get(self, model: type[DebateSession], obj_id: int) -> DebateSession:
        return self.session

    def add(self, obj: DebateMessage) -> None:
        self.messages.append(obj)

    async def commit(self) -> None:
        pass


async def main() -> None:
    topic = " ".join(sys.argv[1:]).strip() or DEFAULT_TOPIC
    user = SimpleNamespace(id=1)

    async def fake_tier(user_id: int) -> Tier:
        return Tier.T2

    async def fake_context(topic: str) -> RAGContext:
        try:
            documents = await debate_router._search_news_documents(topic)
        except ExternalServiceError as exc:
            print(f"\n[notice] 실제 뉴스 검색 실패: {exc.message}")
            documents = []
        if not documents:
            print("\n[notice] 실제 뉴스 검색 결과가 없습니다.")
        return RAGContext(documents=documents, query=topic)

    async def fake_publish(event: object) -> None:
        print(f"\n[event_bus] {event.event_type} session={int(event.debate_session_id)}")

    debate_router.user_context.get_tier = fake_tier
    debate_router._retrieve_context = fake_context
    debate_router.event_bus.publish = fake_publish

    if not debate_service.is_llm_ready():
        print("[notice] LLM API 키가 없어 fallback 토론 생성을 확인합니다.")

    print("== personas ==")
    for persona in await debate_router.personas(user):
        print(f"- {persona.id}: {persona.name} / {persona.stance}")

    start_db = FakeStartDB()
    start = await debate_router.start_debate(
        debate_router.DebateStartRequest(topic=topic),
        user,
        start_db,
    )
    print("\n== start ==")
    print(start.model_dump())

    assert start_db.session is not None
    stream_db = FakeStreamDB(start_db.session)
    response = await debate_router.stream_debate(start.debate_session_id, user, stream_db)

    print("\n== stream ==")
    async for item in response.body_iterator:
        event = item["event"]
        data = json.loads(item["data"])
        if event == "delta":
            print(data["delta"], end="")
        else:
            print(f"\n[{event}] {data}")


if __name__ == "__main__":
    asyncio.run(main())
