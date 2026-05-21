import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from core.auth import router as auth_router
from core.config import settings
from core.contracts import MessageRole
from core.db import engine
from core.event_bus import event_bus
from core.exceptions import register_exception_handlers
from core.jobs import start_scheduler, stop_scheduler
from core.llm import Message, llm
from core.logging import setup_logging
from core.middlewares import LoggingMiddleware, RequestIdMiddleware
from core.push import push
from core.push import router as push_router
from core.user_context import user_context  # noqa: F401  (event handler 등록 트리거)
from features.content import router as content_router
from features.daily_report import router as daily_report_router
from features.debate import router as debate_router
from features.growth import router as growth_router
from features.learning import router as learning_router
from features.onboarding import router as onboarding_router

setup_logging()
logger = logging.getLogger("main")

_DEV_LOCAL_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("startup")
    await event_bus.start()
    await start_scheduler()
    push.init()
    yield
    logger.info("shutdown")
    push.shutdown()
    await stop_scheduler()
    await event_bus.stop()
    await engine.dispose()


app = FastAPI(
    title="Mentors Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=_DEV_LOCAL_ORIGIN_REGEX if settings.env == "dev" else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(push_router)
app.include_router(onboarding_router)
app.include_router(learning_router)
app.include_router(growth_router)
app.include_router(debate_router)
app.include_router(content_router)
app.include_router(daily_report_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str | dict[str, str]]:
    deps: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        deps["db"] = "ok"
    except Exception as e:  # noqa: BLE001
        deps["db"] = f"down: {type(e).__name__}"
    deps["llm"] = "configured" if llm.configured else "no_key"
    overall = "ready" if deps.get("db") == "ok" else "degraded"
    return {"status": overall, "dependencies": deps}


# === Dev-only debug endpoints (ADR-012 SSE 시범) ===
if settings.env == "dev":

    class LLMStreamRequest(BaseModel):
        message: str

    @app.post("/debug/llm-stream", tags=["debug"])
    async def llm_stream_debug(req: LLMStreamRequest) -> EventSourceResponse:
        """SSE 시범 — API 키 없으면 fake stream으로 폴백."""

        async def event_gen() -> AsyncIterator[dict[str, str]]:
            if llm.configured:
                async for chunk in llm.chat_stream(
                    [Message(role=MessageRole.USER, content=req.message)]
                ):
                    yield {
                        "event": "done" if chunk.done else "delta",
                        "data": chunk.model_dump_json(),
                    }
            else:
                # FE 통합 검증용 fake stream
                for word in req.message.split():
                    yield {
                        "event": "delta",
                        "data": json.dumps({"delta": word + " ", "done": False}),
                    }
                    await asyncio.sleep(0.05)
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {
                            "delta": "",
                            "done": True,
                            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                            "_note": "fake stream (no LLM key)",
                        }
                    ),
                }

        return EventSourceResponse(event_gen())
