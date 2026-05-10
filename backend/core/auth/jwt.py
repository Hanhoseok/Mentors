from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from core.config import settings
from core.exceptions import UnauthorizedError


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    encoded: str = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded


def decode_token(token: str) -> dict[str, Any]:
    try:
        decoded: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as e:
        raise UnauthorizedError("Invalid token") from e
    return decoded
