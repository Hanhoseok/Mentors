from __future__ import annotations

import json
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.contracts import MentorId, OnboardingCompletedEvent, Tier, UserId
from core.event_bus import event_bus
from core.exceptions import BadRequestError

from .catalog import (
    MentorCatalogEntry,
    get_catalog_mentor_by_id,
    get_catalog_mentor_by_slug,
    list_catalog_mentors,
)
from .models import OnboardingSurveyAnswer, UserProfile
from .schemas import (
    MentorSummaryResponse,
    OnboardingProfileRequest,
    OnboardingProfileResponse,
    OnboardingProfileSummary,
    OnboardingStatusResponse,
    SelectedMentorResponse,
)

_RISK_WEIGHT = 4
_EXPERIENCE_WEIGHT = 3
_GOAL_WEIGHT = 2
_STYLE_WEIGHT = 1
_INTEREST_WEIGHT = 1


def get_mentor_by_id(mentor_id: int) -> MentorCatalogEntry | None:
    return get_catalog_mentor_by_id(mentor_id)


def recommend_mentors(profile: OnboardingProfileRequest) -> list[MentorSummaryResponse]:
    ranked = sorted(
        (
            (
                _score_mentor(entry, profile),
                entry,
            )
            for entry in list_catalog_mentors()
        ),
        key=lambda item: (-item[0], item[1].id),
    )
    return [
        MentorSummaryResponse(
            id=entry.id,
            slug=entry.slug,
            name=entry.name,
            title=entry.title,
            summary=entry.summary,
            reason=_build_recommendation_reason(entry, profile),
        )
        for _, entry in ranked
    ]


async def get_onboarding_status(
    user_id: UserId,
    db: AsyncSession,
) -> OnboardingStatusResponse:
    profile = await _get_profile(db, user_id)
    if profile is None:
        return OnboardingStatusResponse(onboarded=False)

    return OnboardingStatusResponse(
        onboarded=profile.onboarding_completed_at is not None,
        tier=_coerce_tier(profile.current_tier),
        selected_mentor=_build_selected_mentor(profile),
        completed_at=profile.onboarding_completed_at,
    )


async def save_onboarding_profile(
    user_id: UserId,
    payload: OnboardingProfileRequest,
    db: AsyncSession,
) -> OnboardingProfileResponse:
    profile = await _ensure_profile(db, user_id)

    profile.current_tier = profile.current_tier or Tier.T1.value
    profile.experience_level = payload.experience_level
    profile.risk_profile = payload.risk_profile
    profile.learning_goal = payload.learning_goal
    profile.preferred_style = payload.preferred_style
    profile.interests_json = json.dumps(payload.interests, ensure_ascii=False)

    await db.execute(
        delete(OnboardingSurveyAnswer).where(
            OnboardingSurveyAnswer.user_id == int(user_id)
        )
    )
    for answer in payload.answers:
        db.add(
            OnboardingSurveyAnswer(
                user_id=int(user_id),
                question_code=answer.question_code,
                question_text=answer.question_text,
                answer_value=answer.answer_value,
                answer_payload_json=(
                    json.dumps(answer.answer_payload, ensure_ascii=False)
                    if answer.answer_payload is not None
                    else None
                ),
            )
        )

    await db.commit()

    return OnboardingProfileResponse(
        profile=_build_profile_summary(payload),
        recommended_mentors=recommend_mentors(payload),
    )


async def select_onboarding_mentor(
    user_id: UserId,
    mentor_id: int,
    db: AsyncSession,
) -> OnboardingStatusResponse:
    profile = await _get_profile(db, user_id)
    if profile is None:
        raise BadRequestError("Save your onboarding profile before selecting a mentor.")

    mentor = get_mentor_by_id(mentor_id)
    if mentor is None:
        raise BadRequestError("Unknown mentor_id.")

    profile.current_tier = Tier.T1.value
    profile.selected_mentor_id = mentor.id
    profile.selected_mentor_slug = mentor.slug
    profile.onboarding_completed_at = datetime.now(UTC)

    await db.commit()

    await event_bus.publish(
        OnboardingCompletedEvent(
            user_id=user_id,
            initial_tier=Tier.T1,
            selected_mentor_id=MentorId(mentor.id),
        )
    )

    return OnboardingStatusResponse(
        onboarded=True,
        tier=Tier.T1,
        selected_mentor=SelectedMentorResponse(
            id=mentor.id,
            slug=mentor.slug,
            name=mentor.name,
        ),
        completed_at=profile.onboarding_completed_at,
    )


def _score_mentor(entry: MentorCatalogEntry, profile: OnboardingProfileRequest) -> int:
    score = 0
    if profile.risk_profile in entry.risk_match:
        score += _RISK_WEIGHT
    if profile.experience_level in entry.experience_match:
        score += _EXPERIENCE_WEIGHT
    if profile.learning_goal in entry.goal_match:
        score += _GOAL_WEIGHT
    if profile.preferred_style in entry.style_match:
        score += _STYLE_WEIGHT
    shared_interests = set(profile.interests) & set(entry.interest_match)
    score += len(shared_interests) * _INTEREST_WEIGHT
    return score


def _build_recommendation_reason(
    entry: MentorCatalogEntry,
    profile: OnboardingProfileRequest,
) -> str:
    reasons: list[str] = []
    if profile.risk_profile in entry.risk_match:
        reasons.append(f"fits a {profile.risk_profile} risk profile")
    if profile.experience_level in entry.experience_match:
        reasons.append(f"works well for {profile.experience_level} investors")
    if profile.learning_goal in entry.goal_match:
        reasons.append(f"supports the goal to {profile.learning_goal}")

    shared_interests = sorted(set(profile.interests) & set(entry.interest_match))
    if shared_interests:
        reasons.append(f"matches interests like {', '.join(shared_interests)}")

    if profile.preferred_style in entry.style_match:
        reasons.append(f"leans into a {profile.preferred_style} teaching style")

    if not reasons:
        return f"{entry.name} offers a solid starting point for this profile."
    return f"{entry.name} is recommended because it " + "; ".join(reasons) + "."


def _build_profile_summary(payload: OnboardingProfileRequest) -> OnboardingProfileSummary:
    return OnboardingProfileSummary(
        experience_level=payload.experience_level,
        interests=payload.interests,
        risk_profile=payload.risk_profile,
        learning_goal=payload.learning_goal,
        preferred_style=payload.preferred_style,
    )


def _build_selected_mentor(profile: UserProfile) -> SelectedMentorResponse | None:
    if profile.selected_mentor_id is None:
        return None

    mentor = get_catalog_mentor_by_id(profile.selected_mentor_id)
    if mentor is None:
        mentor = get_catalog_mentor_by_slug(profile.selected_mentor_slug)
    if mentor is None:
        return None

    return SelectedMentorResponse(
        id=mentor.id,
        slug=mentor.slug,
        name=mentor.name,
    )


async def _ensure_profile(db: AsyncSession, user_id: UserId) -> UserProfile:
    profile = await _get_profile(db, user_id)
    if profile is not None:
        return profile

    available_columns = await _get_table_columns(db, "user_profiles")
    legacy_level_id = None
    if "current_level_id" in available_columns:
        legacy_level_id = await _get_level_one_id(db)

    insert_values = _build_profile_insert_values(
        user_id,
        available_columns=available_columns,
        legacy_level_id=legacy_level_id,
    )
    await db.execute(_build_profile_insert_statement(tuple(insert_values)), insert_values)

    profile = await _get_profile(db, user_id)
    if profile is None:
        raise RuntimeError("Failed to initialize onboarding profile row.")
    return profile


async def _get_profile(db: AsyncSession, user_id: UserId) -> UserProfile | None:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == int(user_id))
    )
    return result.scalar_one_or_none()


async def _get_table_columns(db: AsyncSession, table_name: str) -> set[str]:
    connection = await db.connection()
    return await connection.run_sync(
        lambda sync_conn: {
            column["name"] for column in sa.inspect(sync_conn).get_columns(table_name)
        }
    )


async def _get_level_one_id(db: AsyncSession) -> int:
    result = await db.execute(
        text(
            "SELECT id FROM level_definitions "
            "WHERE level_no = :level_no ORDER BY id LIMIT 1"
        ),
        {"level_no": 1},
    )
    level_id = result.scalar_one_or_none()
    if level_id is None:
        raise BadRequestError("Level 1 definition is missing.")
    return int(level_id)


def _build_profile_insert_values(
    user_id: UserId,
    *,
    available_columns: set[str],
    legacy_level_id: int | None,
) -> dict[str, object]:
    values: dict[str, object] = {"user_id": int(user_id), "current_tier": Tier.T1.value}
    if legacy_level_id is not None:
        legacy_defaults: dict[str, object] = {
            "current_level_id": legacy_level_id,
            "learning_stage": "LEARNING",
            "has_investment_experience": False,
            "total_xp": 0,
        }
        for key, value in legacy_defaults.items():
            if key in available_columns:
                values[key] = value

    return {
        key: value for key, value in values.items() if key in available_columns
    }


def _build_profile_insert_statement(column_names: tuple[str, ...]) -> sa.TextClause:
    columns_sql = ", ".join(column_names)
    params_sql = ", ".join(f":{name}" for name in column_names)
    return text(f"INSERT INTO user_profiles ({columns_sql}) VALUES ({params_sql})")


def _coerce_tier(raw_tier: str | None) -> Tier | None:
    if raw_tier is None:
        return None
    try:
        return Tier(raw_tier)
    except ValueError:
        return None


__all__ = [
    "get_mentor_by_id",
    "get_onboarding_status",
    "recommend_mentors",
    "save_onboarding_profile",
    "select_onboarding_mentor",
]
