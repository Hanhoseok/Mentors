"""FCM 푸시 클라이언트 (§4.15).

FCM_CREDENTIALS_PATH 미설정 시 모든 send는 no-op (로그만). dev에서 푸시 끄기 가능.
"""

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select

from core.config import settings
from core.contracts import UserId
from core.db import SessionLocal

from .models import DeviceToken

logger = logging.getLogger("push")


class Push:
    def __init__(self) -> None:
        self._app: Any | None = None

    def init(self) -> None:
        """앱 lifespan에서 호출."""
        if not settings.fcm_credentials_path:
            logger.info("push.init_skipped", extra={"reason": "FCM_CREDENTIALS_PATH not set"})
            return
        try:
            from firebase_admin import credentials, initialize_app

            cred = credentials.Certificate(settings.fcm_credentials_path)
            self._app = initialize_app(cred)
            logger.info("push.initialized")
        except Exception:
            logger.exception("push.init_failed")
            self._app = None

    def shutdown(self) -> None:
        if self._app is None:
            return
        try:
            from firebase_admin import delete_app

            delete_app(self._app)
        except Exception:
            logger.exception("push.shutdown_failed")
        self._app = None

    @property
    def configured(self) -> bool:
        return self._app is not None

    async def send_to_user(
        self,
        user_id: UserId,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> int:
        return await self.send_to_users([user_id], title, body, data)

    async def send_to_users(
        self,
        user_ids: list[UserId],
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> int:
        if not user_ids:
            return 0

        async with SessionLocal() as session:
            stmt = select(DeviceToken).where(DeviceToken.user_id.in_(user_ids))
            tokens = (await session.execute(stmt)).scalars().all()

        if not tokens:
            logger.info("push.no_tokens", extra={"user_count": len(user_ids)})
            return 0

        if not self.configured:
            logger.info(
                "push.skipped_unconfigured",
                extra={"token_count": len(tokens), "title": title},
            )
            return 0

        try:
            from firebase_admin import messaging

            message = messaging.MulticastMessage(
                tokens=[t.fcm_token for t in tokens],
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
            )
            response = messaging.send_each_for_multicast(message)
        except Exception:
            logger.exception("push.send_failed", extra={"token_count": len(tokens)})
            return 0

        success_count: int = response.success_count
        await self._cleanup_invalid_tokens(tokens, response)
        return success_count

    async def _cleanup_invalid_tokens(self, tokens: Sequence[DeviceToken], response: Any) -> None:
        invalid_ids: list[int] = []
        for idx, resp in enumerate(response.responses):
            if not resp.success and resp.exception is not None:
                code = getattr(resp.exception, "code", "")
                if code in (
                    "UNREGISTERED",
                    "INVALID_ARGUMENT",
                    "registration-token-not-registered",
                ):
                    invalid_ids.append(tokens[idx].id)

        if not invalid_ids:
            return

        async with SessionLocal() as session:
            for tid in invalid_ids:
                stale = await session.get(DeviceToken, tid)
                if stale is not None:
                    await session.delete(stale)
            await session.commit()
        logger.info("push.invalid_tokens_removed", extra={"count": len(invalid_ids)})


push = Push()
