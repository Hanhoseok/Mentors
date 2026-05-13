"""EventBus — Redis Pub/Sub fire-and-forget (§4.5, ADR-008).

핸들러는 반드시 멱등이어야 한다 (§7.4, AGENTS.md §5.4).
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import redis.asyncio as redis

from core.config import settings
from core.contracts.events import BaseEvent

logger = logging.getLogger("event_bus")

E = TypeVar("E", bound=BaseEvent)
EventHandler = Callable[[Any], Awaitable[None]]
_HandlerEntry = tuple[type[BaseEvent], EventHandler]


def _channel(event_type: str) -> str:
    return f"events:{event_type}"


def _event_type_of(event_class: type[BaseEvent]) -> str:
    field = event_class.model_fields.get("event_type")
    if field is None:
        raise TypeError(f"{event_class.__name__} has no event_type field")
    default = field.default
    if not isinstance(default, str):
        raise TypeError(
            f"{event_class.__name__}.event_type has no Literal string default; got {default!r}"
        )
    return default


class EventBus:
    def __init__(self) -> None:
        self._client: redis.Redis | None = None
        self._pubsub: Any | None = None
        self._handlers: dict[str, list[_HandlerEntry]] = {}
        self._listener_task: asyncio.Task[None] | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    async def publish(self, event: BaseEvent) -> None:
        try:
            await self.client.publish(_channel(event.event_type), event.model_dump_json())
        except Exception:
            logger.exception(
                "event_publish_failed",
                extra={"event_type": event.event_type, "event_id": event.event_id},
            )

    def subscribe(self, event_class: type[E], handler: Callable[[E], Awaitable[None]]) -> None:
        type_name = _event_type_of(event_class)
        self._handlers.setdefault(type_name, []).append((event_class, handler))

    async def start(self) -> None:
        if not self._handlers:
            logger.info("event_bus.start_skipped", extra={"reason": "no handlers registered"})
            return
        try:
            self._pubsub = self.client.pubsub()
            channels = [_channel(t) for t in self._handlers]
            await self._pubsub.subscribe(*channels)
        except Exception:
            logger.exception("event_bus.start_failed")
            self._pubsub = None
            return
        self._listener_task = asyncio.create_task(self._listen(), name="event_bus_listener")
        logger.info("event_bus.started", extra={"channel_count": len(self._handlers)})

    async def stop(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:
                logger.exception("event_bus.pubsub_close_failed")
            self._pubsub = None
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                logger.exception("event_bus.client_close_failed")
            self._client = None
        logger.info("event_bus.stopped")

    async def _listen(self) -> None:
        assert self._pubsub is not None
        try:
            async for message in self._pubsub.listen():
                if message.get("type") != "message":
                    continue
                await self._dispatch(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("event_bus.listener_crashed")

    async def _dispatch(self, message: dict[str, Any]) -> None:
        raw = message.get("data")
        if not isinstance(raw, str):
            logger.warning("event_invalid_payload", extra={"channel": message.get("channel")})
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("event_invalid_json", extra={"channel": message.get("channel")})
            return

        event_type = data.get("event_type") if isinstance(data, dict) else None
        if not isinstance(event_type, str):
            logger.warning("event_missing_type", extra={"channel": message.get("channel")})
            return

        for event_class, handler in self._handlers.get(event_type, []):
            try:
                event = event_class.model_validate(data)
                await handler(event)
            except Exception:
                logger.exception(
                    "event_handler_failed",
                    extra={
                        "event_type": event_type,
                        "event_id": data.get("event_id"),
                        "handler": handler.__qualname__,
                    },
                )


event_bus = EventBus()
