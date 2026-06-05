import asyncio
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel

from core.config import settings
from core.exceptions import ExternalServiceError, UnauthorizedError

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleUserInfo(BaseModel):
    sub: str  # Google's user ID (provider_user_id)
    email: str
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def get_authorization_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> GoogleUserInfo:
    async with httpx.AsyncClient(timeout=10.0) as client:
        access_token = await _exchange_access_token(
            client,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        return await _fetch_userinfo(client, access_token)


async def exchange_mobile_code(
    *,
    code: str,
    client_id: str,
    redirect_uri: str,
    code_verifier: str,
) -> GoogleUserInfo:
    async with httpx.AsyncClient(timeout=10.0) as client:
        access_token = await _exchange_access_token(
            client,
            data={
                "code": code,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
            },
        )
        return await _fetch_userinfo(client, access_token)


async def verify_google_id_token(*, id_token: str) -> GoogleUserInfo:
    audience = _resolved_google_web_client_id()
    if audience is None:
        raise UnauthorizedError("Google mobile login is not configured")

    try:
        claims = await asyncio.to_thread(_verify_google_id_token_sync, id_token, audience)
    except ValueError as exc:
        raise UnauthorizedError("Invalid Google ID token") from exc

    email = claims.get("email")
    sub = claims.get("sub")
    if not isinstance(email, str) or not email or not isinstance(sub, str) or not sub:
        raise UnauthorizedError("Google ID token missing required claims")

    return GoogleUserInfo(
        sub=sub,
        email=email,
        email_verified=bool(claims.get("email_verified", False)),
        name=_optional_string(claims.get("name")),
        picture=_optional_string(claims.get("picture")),
    )


async def _exchange_access_token(
    client: httpx.AsyncClient,
    *,
    data: dict[str, str],
) -> str:
    try:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data=data,
        )
    except httpx.HTTPError as e:
        raise ExternalServiceError("Google token exchange failed") from e

    if token_resp.status_code != 200:
        raise UnauthorizedError("OAuth code exchange failed")

    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise UnauthorizedError("No access_token from Google")

    return access_token


async def _fetch_userinfo(client: httpx.AsyncClient, access_token: str) -> GoogleUserInfo:
    try:
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    except httpx.HTTPError as e:
        raise ExternalServiceError("Google userinfo fetch failed") from e

    if userinfo_resp.status_code != 200:
        raise ExternalServiceError("Google userinfo failed")

    return GoogleUserInfo.model_validate(userinfo_resp.json())


def _verify_google_id_token_sync(id_token: str, audience: str) -> dict[str, Any]:
    return dict(
        google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            audience=audience,
        )
    )


def _resolved_google_web_client_id() -> str | None:
    normalized = settings.google_client_id.strip()
    return normalized or None


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
