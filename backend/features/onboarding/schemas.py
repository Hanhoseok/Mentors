from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from core.contracts import Tier


class SurveyAnswerRequest(BaseModel):
    question_code: str = Field(min_length=1, max_length=100)
    question_text: str | None = Field(default=None, max_length=255)
    answer_value: str | None = None
    answer_payload: dict[str, Any] | None = None


class OnboardingProfileRequest(BaseModel):
    experience_level: str = Field(min_length=1, max_length=50)
    interests: list[str] = Field(min_length=1)
    risk_profile: str = Field(min_length=1, max_length=50)
    learning_goal: str = Field(min_length=1, max_length=100)
    preferred_style: str = Field(min_length=1, max_length=50)
    answers: list[SurveyAnswerRequest] = Field(default_factory=list)

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, interests: list[str]) -> list[str]:
        cleaned: list[str] = []
        for interest in interests:
            value = interest.strip()
            if not value:
                continue
            if value not in cleaned:
                cleaned.append(value)
        if not cleaned:
            raise ValueError("At least one interest is required")
        return cleaned


class OnboardingProfileSummary(BaseModel):
    experience_level: str
    interests: list[str]
    risk_profile: str
    learning_goal: str
    preferred_style: str


class MentorSummaryResponse(BaseModel):
    id: int
    slug: str
    name: str
    title: str
    summary: str
    reason: str


class SelectedMentorResponse(BaseModel):
    id: int
    slug: str
    name: str


class OnboardingProfileResponse(BaseModel):
    profile: OnboardingProfileSummary
    recommended_mentors: list[MentorSummaryResponse]


class OnboardingStatusResponse(BaseModel):
    onboarded: bool
    tier: Tier | None = None
    selected_mentor: SelectedMentorResponse | None = None
    completed_at: datetime | None = None


class SelectMentorRequest(BaseModel):
    mentor_id: int


__all__ = [
    "MentorSummaryResponse",
    "OnboardingProfileRequest",
    "OnboardingProfileResponse",
    "OnboardingProfileSummary",
    "OnboardingStatusResponse",
    "SelectMentorRequest",
    "SelectedMentorResponse",
    "SurveyAnswerRequest",
]
