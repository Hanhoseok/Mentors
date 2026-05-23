from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.exceptions import ForbiddenError, UnauthorizedError

from .jwt import decode_token
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/local/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise UnauthorizedError("Missing token")

    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Invalid token payload")

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as e:
        raise UnauthorizedError("Invalid token sub") from e

    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    if user.status == "suspended":
        raise ForbiddenError("Account suspended")
    if user.status == "deleted":
        raise ForbiddenError("Account deleted")

    return user
