from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.exceptions import LockError

from core.config import settings

_pool: redis.ConnectionPool | None = None


def _get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
    return _pool


class Cache:
    def __init__(self, namespace: str) -> None:
        self.namespace = namespace
        self._client = redis.Redis(connection_pool=_get_pool())

    def _key(self, key: str) -> str:
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> str | None:
        result = await self._client.get(self._key(key))
        return result if result is None else str(result)

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        await self._client.set(self._key(key), value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(self._key(key))

    @asynccontextmanager
    async def lock(self, key: str, ttl: int = 10) -> AsyncIterator[None]:
        lock = self._client.lock(self._key(f"lock:{key}"), timeout=ttl)
        await lock.acquire()
        try:
            yield
        finally:
            try:
                await lock.release()
            except LockError:
                pass


def make_cache(namespace: str) -> Cache:
    return Cache(namespace)
