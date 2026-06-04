import json
import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import make_cache
from core.config import settings
from core.contracts import Tier, UserId, UserSignedUpEvent, UserUpdatedEvent
from core.db import get_db
from core.event_bus import event_bus
from core.exceptions import (
    BadRequestError,
    ConflictError,
    DomainError,
    ForbiddenError,
    UnauthorizedError,
)
from core.user_context import user_context

from .dependencies import get_current_user
from .jwt import create_access_token
from .models import AuthIdentity, LocalCredential, User
from .oauth_google import (
    GoogleUserInfo,
    exchange_code,
    generate_state,
    get_authorization_url,
)
from .passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("auth")

_state_cache = make_cache("auth")
STATE_TTL_S = 600
DEV_LOCAL_ACCOUNT_EMAIL = "local-test@mentors.dev"
DEV_LOCAL_ACCOUNT_PASSWORD = "Mentors123!"
DEV_LOCAL_ACCOUNT_NICKNAME = "local-tester"


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
    tier: Tier | None = None


class DevTokenResponse(TokenResponse):
    user: UserResponse
    created: bool
    tier: Tier | None = None


class LocalSignupRequest(BaseModel):
    email: str
    password: str
    password_confirm: str


class LocalLoginRequest(BaseModel):
    email: str
    password: str


@router.get("/google/login")
async def google_login(return_to: str | None = Query(default=None)) -> RedirectResponse:
    if return_to is not None and not _is_safe_return_to(return_to):
        raise BadRequestError("허용되지 않은 로그인 복귀 경로입니다.")

    state = generate_state()
    await _state_cache.set(
        f"state:{state}",
        json.dumps({"return_to": return_to}),
        ttl=STATE_TTL_S,
    )
    url = get_authorization_url(state)
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse | RedirectResponse:
    saved = await _state_cache.get(f"state:{state}")
    if saved is None:
        raise UnauthorizedError("Invalid or expired state")
    await _state_cache.delete(f"state:{state}")
    return_to = _read_return_to(saved)

    try:
        info = await exchange_code(code)
        user, is_new = await _upsert_user(db, info)
    except DomainError as exc:
        if return_to is not None:
            return RedirectResponse(
                url=_build_return_to_url(return_to, error=exc.message),
                status_code=302,
            )
        raise

    if is_new:
        await event_bus.publish(UserSignedUpEvent(user_id=UserId(user.id)))

    token = create_access_token(user.id)
    logger.info("user_login", extra={"user_id": user.id, "is_new": is_new})
    if return_to is not None:
        return RedirectResponse(
            url=_build_return_to_url(return_to, token=token, is_new=is_new),
            status_code=302,
        )

    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/local/signup", response_model=TokenResponse)
async def local_signup(
    req: LocalSignupRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    email = _normalize_email(req.email)
    _validate_signup_password(req.password, req.password_confirm)

    user, is_new = await _create_or_attach_local_account(
        db,
        email=email,
        password=req.password,
    )
    if is_new:
        await event_bus.publish(UserSignedUpEvent(user_id=UserId(user.id)))

    token = create_access_token(user.id)
    logger.info("user_login", extra={"user_id": user.id, "is_new": is_new, "provider": "local"})
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/local/login", response_model=TokenResponse)
async def local_login(
    req: LocalLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    email = _normalize_email(req.email)
    if email == DEV_LOCAL_ACCOUNT_EMAIL:
        await _ensure_dev_dummy_local_account(db)

    user = await _find_user_by_email(db, email)
    invalid_credentials_error = UnauthorizedError("이메일 또는 비밀번호가 올바르지 않습니다.")

    if user is None:
        raise invalid_credentials_error

    google_identity = await _find_google_identity_for_user(db, user.id)
    if google_identity is not None:
        raise ConflictError(
            "이 이메일은 Google 로그인으로 가입된 계정입니다. Google 로그인으로 이용해 주세요."
        )

    credential = await _find_local_credential_for_user(db, user.id)
    if credential is None:
        raise invalid_credentials_error
    if not verify_password(req.password, credential.password_hash):
        raise invalid_credentials_error

    token = create_access_token(user.id)
    logger.info("user_login", extra={"user_id": user.id, "is_new": False, "provider": "local"})
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

    if req.tier is not None:
        await _apply_dev_tier(db, user_id=user.id, tier=req.tier)
        await user_context.invalidate(UserId(user.id))

    token = create_access_token(user.id)
    return DevTokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserResponse.from_user(user),
        created=created,
        tier=req.tier,
    )


async def _apply_dev_tier(db: AsyncSession, *, user_id: int, tier: Tier) -> None:
    await db.execute(
        text(
            """
            INSERT INTO user_profiles (user_id, current_tier)
            VALUES (:user_id, :tier)
            ON CONFLICT (user_id)
            DO UPDATE SET current_tier = EXCLUDED.current_tier,
                          updated_at = now()
            """
        ),
        {"user_id": user_id, "tier": tier.value},
    )
    await db.execute(
        text(
            """
            INSERT INTO tier_states (user_id, current_tier)
            VALUES (:user_id, :tier)
            ON CONFLICT (user_id)
            DO UPDATE SET current_tier = EXCLUDED.current_tier,
                          updated_at = now()
            """
        ),
        {"user_id": user_id, "tier": tier.value},
    )
    await db.commit()


async def _upsert_user(db: AsyncSession, info: GoogleUserInfo) -> tuple[User, bool]:
    identity = await _find_google_identity_by_sub(db, info.sub)

    if identity is not None:
        user = await db.get(User, identity.user_id)
        if user is None:
            raise UnauthorizedError("Identity exists but user missing")
        return user, False

    existing_user = await _find_user_by_email(db, _normalize_email(info.email))
    if existing_user is not None:
        local_credential = await _find_local_credential_for_user(db, existing_user.id)
        if local_credential is not None:
            raise ConflictError(
                "이 이메일은 이미 로컬 계정으로 가입된 상태입니다. 이메일 로그인으로 이용해 주세요."
            )

        google_identity = await _find_google_identity_for_user(db, existing_user.id)
        if google_identity is not None:
            raise ConflictError("이 이메일은 다른 Google 계정에 연결되어 있습니다.")

        await _create_google_identity(db, user_id=existing_user.id, provider_user_id=info.sub)
        await db.commit()
        await db.refresh(existing_user)
        return existing_user, False

    await _sync_pk_sequence(db, table_name="users", sequence_name="users_id_seq")
    user = User(
        email=_normalize_email(info.email),
        nickname=info.name or info.email.split("@")[0],
        status="active",
    )
    db.add(user)
    await db.flush()

    await _create_google_identity(db, user_id=user.id, provider_user_id=info.sub)
    await db.commit()
    await db.refresh(user)
    return user, True


async def _create_or_attach_local_account(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> tuple[User, bool]:
    existing_user = await _find_user_by_email(db, email)
    if existing_user is not None:
        local_credential = await _find_local_credential_for_user(db, existing_user.id)
        if local_credential is not None:
            raise ConflictError("이미 가입된 이메일입니다.")

        google_identity = await _find_google_identity_for_user(db, existing_user.id)
        if google_identity is not None:
            raise ConflictError(
                "이 이메일은 Google 로그인으로 가입된 계정입니다. Google 로그인으로 이용해 주세요."
            )

        await _create_local_credential(db, user_id=existing_user.id, password=password)
        await db.commit()
        await db.refresh(existing_user)
        return existing_user, False

    await _sync_pk_sequence(db, table_name="users", sequence_name="users_id_seq")
    user = User(
        email=email,
        nickname=_nickname_from_email(email),
        status="active",
    )
    db.add(user)
    await db.flush()
    await _create_local_credential(db, user_id=user.id, password=password)
    await db.commit()
    await db.refresh(user)
    return user, True


async def _create_local_credential(
    db: AsyncSession,
    *,
    user_id: int,
    password: str,
) -> None:
    await _sync_pk_sequence(
        db,
        table_name="local_credentials",
        sequence_name="local_credentials_id_seq",
    )
    db.add(
        LocalCredential(
            user_id=user_id,
            password_hash=hash_password(password),
        )
    )


async def _create_google_identity(
    db: AsyncSession,
    *,
    user_id: int,
    provider_user_id: str,
) -> None:
    await _sync_pk_sequence(
        db,
        table_name="auth_identities",
        sequence_name="auth_identities_id_seq",
    )
    db.add(
        AuthIdentity(
            user_id=user_id,
            provider="google",
            provider_user_id=provider_user_id,
        )
    )


async def _ensure_dev_dummy_local_account(db: AsyncSession) -> None:
    if settings.env != "dev":
        return

    user = await _find_user_by_email(db, DEV_LOCAL_ACCOUNT_EMAIL)
    created_user = False

    if user is None:
        await _sync_pk_sequence(db, table_name="users", sequence_name="users_id_seq")
        user = User(
            email=DEV_LOCAL_ACCOUNT_EMAIL,
            nickname=DEV_LOCAL_ACCOUNT_NICKNAME,
            status="active",
        )
        db.add(user)
        await db.flush()
        created_user = True

    credential = await _find_local_credential_for_user(db, user.id)
    if credential is None:
        await _create_local_credential(
            db,
            user_id=user.id,
            password=DEV_LOCAL_ACCOUNT_PASSWORD,
        )
        await db.commit()
        await db.refresh(user)

    if created_user:
        await event_bus.publish(UserSignedUpEvent(user_id=UserId(user.id)))


async def _find_user_by_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def _find_google_identity_by_sub(db: AsyncSession, google_sub: str) -> AuthIdentity | None:
    return (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == "google",
                AuthIdentity.provider_user_id == google_sub,
            )
        )
    ).scalar_one_or_none()


async def _find_google_identity_for_user(db: AsyncSession, user_id: int) -> AuthIdentity | None:
    return (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user_id,
                AuthIdentity.provider == "google",
            )
        )
    ).scalar_one_or_none()


async def _find_local_credential_for_user(
    db: AsyncSession,
    user_id: int,
) -> LocalCredential | None:
    return (
        await db.execute(select(LocalCredential).where(LocalCredential.user_id == user_id))
    ).scalar_one_or_none()


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise BadRequestError("올바른 이메일을 입력해 주세요.")
    return normalized


def _validate_signup_password(password: str, password_confirm: str) -> None:
    if len(password) < 8 or not password.strip():
        raise BadRequestError("비밀번호는 8자 이상으로 입력해 주세요.")
    if password != password_confirm:
        raise BadRequestError("비밀번호 확인이 일치하지 않습니다.")


def _nickname_from_email(email: str) -> str:
    local_part = email.split("@")[0].strip()
    return (local_part or "mentor-user")[:50]


def _read_return_to(saved_state: str) -> str | None:
    try:
        payload = json.loads(saved_state)
    except json.JSONDecodeError:
        return None

    return_to = payload.get("return_to")
    if not isinstance(return_to, str) or not return_to:
        return None
    if not _is_safe_return_to(return_to):
        return None
    return return_to


def _is_safe_return_to(return_to: str) -> bool:
    parsed = urlparse(return_to)
    if parsed.scheme == "mentors":
        return parsed.netloc == "auth"
    if parsed.scheme in {"http", "https"}:
        return parsed.hostname in {"localhost", "127.0.0.1"}
    return False


def _build_return_to_url(
    return_to: str,
    *,
    token: str | None = None,
    error: str | None = None,
    is_new: bool | None = None,
) -> str:
    parsed = urlparse(return_to)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if token is not None:
        params["token"] = token
    if error is not None:
        params["error"] = error
    if is_new is not None:
        params["is_new"] = "1" if is_new else "0"

    return urlunparse(parsed._replace(query=urlencode(params)))


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


@router.delete("/me", status_code=204)
async def delete_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    user.status = "deleted"
    await db.commit()
    await event_bus.publish(UserUpdatedEvent(user_id=UserId(user.id), fields=["status"]))
    return Response(status_code=204)
