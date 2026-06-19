import pytest

from features.onboarding.schemas import OnboardingProfileRequest
from features.onboarding.service import (
    _build_profile_insert_statement,
    _build_profile_insert_values,
    get_mentor_by_id,
    recommend_mentors,
)


def test_recommend_mentors_prefers_buffett_for_steady_value_profile() -> None:
    profile = OnboardingProfileRequest(
        experience_level="beginner",
        interests=["value", "dividend"],
        risk_profile="steady",
        learning_goal="build-habit",
        preferred_style="gentle",
    )

    recommendations = recommend_mentors(profile)

    assert recommendations[0].slug == "warren-buffett"
    assert recommendations[0].name == "워런 버핏"
    assert recommendations[0].reason


def test_recommend_mentors_prefers_bogle_for_dividend_balanced_profile() -> None:
    profile = OnboardingProfileRequest(
        experience_level="steady-builder",
        interests=["dividend", "etf", "long-term"],
        risk_profile="balanced",
        learning_goal="protect-capital",
        preferred_style="patient",
    )

    recommendations = recommend_mentors(profile)

    assert recommendations[0].slug == "john-bogle"
    assert recommendations[0].name == "존 보글"


def test_get_mentor_by_id_returns_none_for_unknown_id() -> None:
    assert get_mentor_by_id(999) is None


def test_profile_request_requires_at_least_one_interest() -> None:
    with pytest.raises(ValueError):
        OnboardingProfileRequest(
            experience_level="beginner",
            interests=[],
            risk_profile="steady",
            learning_goal="build-habit",
            preferred_style="gentle",
        )


def test_build_profile_insert_values_includes_legacy_defaults_when_needed() -> None:
    values = _build_profile_insert_values(
        7,
        available_columns={
            "user_id",
            "current_tier",
            "current_level_id",
            "learning_stage",
            "has_investment_experience",
            "total_xp",
        },
        legacy_level_id=1,
    )

    assert values == {
        "user_id": 7,
        "current_tier": "T1",
        "current_level_id": 1,
        "learning_stage": "LEARNING",
        "has_investment_experience": False,
        "total_xp": 0,
    }


def test_build_profile_insert_statement_targets_requested_columns() -> None:
    statement = _build_profile_insert_statement(
        ("user_id", "current_tier", "current_level_id")
    )

    assert str(statement) == (
        "INSERT INTO user_profiles (user_id, current_tier, current_level_id) "
        "VALUES (:user_id, :current_tier, :current_level_id)"
    )
