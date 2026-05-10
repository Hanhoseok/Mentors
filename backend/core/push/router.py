import logging
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.db import get_db
from core.exceptions import NotFoundError

from .models import DeviceToken

router = APIRouter(prefix="/me/devices", tags=["push"])
logger = logging.getLogger("push.router")


class DeviceRegisterRequest(BaseModel):
    fcm_token: str
    platform: Literal["ios", "android", "web"]


class DeviceResponse(BaseModel):
    id: int
    platform: str


@router.post("", response_model=DeviceResponse, status_code=201)
async def register_device(
    req: DeviceRegisterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceResponse:
    stmt = select(DeviceToken).where(DeviceToken.fcm_token == req.fcm_token)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.user_id = user.id
        existing.platform = req.platform
        await db.commit()
        await db.refresh(existing)
        logger.info("device.reassigned", extra={"user_id": user.id, "device_id": existing.id})
        return DeviceResponse(id=existing.id, platform=existing.platform)

    token = DeviceToken(
        user_id=user.id,
        fcm_token=req.fcm_token,
        platform=req.platform,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    logger.info("device.registered", extra={"user_id": user.id, "device_id": token.id})
    return DeviceResponse(id=token.id, platform=token.platform)


@router.delete("/{device_id}", status_code=204)
async def unregister_device(
    device_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    token = await db.get(DeviceToken, device_id)
    if token is None or token.user_id != user.id:
        raise NotFoundError("Device not found")
    await db.delete(token)
    await db.commit()
    logger.info("device.unregistered", extra={"user_id": user.id, "device_id": device_id})
