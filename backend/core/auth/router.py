import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import make_cache
from core.config import settings
from core.contracts import UserId, UserSignedUpEvent
from core.db import get_db
from core.event_bus import event_bus
from core.exceptions import ForbiddenError, UnauthorizedError

from .dependencies import get_current_user
from .jwt import create_access_token
from .models import AuthIdentity, User
from .oauth_google import (
    GoogleUserInfo,
    exchange_code,
    generate_state,
    get_authorization_url,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("auth")

_state_cache = make_cache("auth")
STATE_TTL_S = 600


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    email: str
    nickname: str
    status: str

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            nickname=user.nickname,
            status=user.status,
        )


class DevTokenRequest(BaseModel):
    email: str | None = None
    nickname: str | None = None


class DevTokenResponse(TokenResponse):
    user: UserResponse
    created: bool


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    state = generate_state()
    await _state_cache.set(f"state:{state}", "1", ttl=STATE_TTL_S)
    url = get_authorization_url(state)
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    saved = await _state_cache.get(f"state:{state}")
    if saved is None:
        raise UnauthorizedError("Invalid or expired state")
    await _state_cache.delete(f"state:{state}")

    info = await exchange_code(code)
    user, is_new = await _upsert_user(db, info)

    if is_new:
        await event_bus.publish(UserSignedUpEvent(user_id=UserId(user.id)))

    token = create_access_token(user.id)
    logger.info("user_login", extra={"user_id": user.id, "is_new": is_new})
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/dev-token", response_model=DevTokenResponse)
async def issue_dev_token(
    req: DevTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> DevTokenResponse:
    if settings.env != "dev":
        raise ForbiddenError("Development token endpoint is disabled.")

    email = req.email or f"dev+{uuid4().hex[:12]}@local.test"
    nickname = req.nickname or f"dev-{email.split('@')[0].split('+')[-1][:6]}"
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    created = False

    if user is None:
        await _sync_pk_sequence(db, table_name="users", sequence_name="users_id_seq")
        user = User(
            email=email,
            nickname=nickname,
            status="active",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        created = True
        await event_bus.publish(UserSignedUpEvent(user_id=UserId(user.id)))

    token = create_access_token(user.id)
    return DevTokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserResponse.from_user(user),
        created=created,
    )


async def _upsert_user(db: AsyncSession, info: GoogleUserInfo) -> tuple[User, bool]:
    stmt = select(AuthIdentity).where(
        AuthIdentity.provider == "google",
        AuthIdentity.provider_user_id == info.sub,
    )
    identity = (await db.execute(stmt)).scalar_one_or_none()

    if identity is not None:
        user = await db.get(User, identity.user_id)
        if user is None:
            raise UnauthorizedError("Identity exists but user missing")
        return user, False

    await _sync_pk_sequence(db, table_name="users", sequence_name="users_id_seq")
    user = User(
        email=info.email,
        nickname=info.name or info.email.split("@")[0],
        status="active",
    )
    db.add(user)
    await db.flush()

    await _sync_pk_sequence(
        db,
        table_name="auth_identities",
        sequence_name="auth_identities_id_seq",
    )
    new_identity = AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_user_id=info.sub,
    )
    db.add(new_identity)
    await db.commit()
    await db.refresh(user)
    return user, True


async def _sync_pk_sequence(
    db: AsyncSession,
    *,
    table_name: str,
    sequence_name: str,
) -> None:
    await db.execute(
        text(
            f"""
            SELECT setval(
                '{sequence_name}',
                COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                EXISTS (SELECT 1 FROM {table_name})
            )
            """
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_user(user)
