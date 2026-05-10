import secrets
from urllib.parse import urlencode

import httpx
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
        try:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        except httpx.HTTPError as e:
            raise ExternalServiceError("Google token exchange failed") from e

        if token_resp.status_code != 200:
            raise UnauthorizedError("OAuth code exchange failed")

        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise UnauthorizedError("No access_token from Google")

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
