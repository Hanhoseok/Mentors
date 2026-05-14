"""Onboarding endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.dependencies import get_current_user
from core.auth.models import User
from core.contracts import UserId
from core.db import get_db

from .schemas import (
    OnboardingProfileRequest,
    OnboardingProfileResponse,
    OnboardingStatusResponse,
    SelectMentorRequest,
)
from .service import (
    get_onboarding_status,
    save_onboarding_profile,
    select_onboarding_mentor,
)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/status", response_model=OnboardingStatusResponse)
async def status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    return await get_onboarding_status(UserId(user.id), db)


@router.post("/profile", response_model=OnboardingProfileResponse)
async def profile(
    payload: OnboardingProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProfileResponse:
    return await save_onboarding_profile(UserId(user.id), payload, db)


@router.post("/select-mentor", response_model=OnboardingStatusResponse)
async def select_mentor(
    payload: SelectMentorRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatusResponse:
    return await select_onboarding_mentor(UserId(user.id), payload.mentor_id, db)
