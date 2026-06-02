"""학습 동 Pydantic 스키마 — 요청/응답 모델."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


# --- 요청 ---
class CreateSessionReq(BaseModel):
    mentor_id: int = Field(..., description="선택한 멘토 ID")


class SendMessageReq(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="사용자 메시지")


class ChatStreamReq(BaseModel):
    session_id: int = Field(..., description="채팅 세션 ID")
    content: str = Field(..., min_length=1, max_length=2000, description="사용자 메시지")


# --- 응답 ---
class SessionRes(BaseModel):
    id: int
    mentor_id: int
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageRes(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionListRes(BaseModel):
    sessions: list[SessionRes]


class MessageListRes(BaseModel):
    messages: list[MessageRes]


# --- 퀴즈 요청/응답 ---
class SubmitQuizReq(BaseModel):
    question_id: str | None = Field(default=None, description="팔로우업 퀴즈 ID")
    concept_id: int | None = Field(default=None, description="투자 개념 ID")
    quiz_index: int | None = Field(default=None, description="같은 개념 안에서의 0기반 문제 인덱스")
    answer_index: int = Field(..., description="선택한 보기 인덱스 (0~3)")

    @model_validator(mode="after")
    def validate_target(self) -> "SubmitQuizReq":
        if self.question_id is None and self.concept_id is None:
            raise ValueError("question_id 또는 concept_id 중 하나는 필요합니다.")
        return self


class QuizOption(BaseModel):
    index: int
    text: str


class QuizRes(BaseModel):
    concept_id: int
    concept_name: str
    question: str
    options: list[QuizOption]


class SubmitQuizRes(BaseModel):
    correct: bool
    explanation: str


class TierQuizItemRes(BaseModel):
    question_id: str
    concept_id: int
    concept_name: str
    quiz_index: int
    question: str
    options: list[QuizOption]
    attempted: bool = False
    solved: bool = False
    last_result_correct: bool | None = None


class CurrentTierQuizzesRes(BaseModel):
    tier: str
    quizzes: list[TierQuizItemRes]


# --- 그날 그 멘토 첫 진입: 일일 리포트 오프너 ---
class DailyReportCard(BaseModel):
    """채팅 진입 시 노출하는 일일 리포트 카드. id로 mentors://report/{id} 딥링크 구성."""

    id: int
    report_date: date
    mentor_strategy: str
    tier: str
    status: str
    body: str | None
    highlights: list[dict[str, Any]]


class TodayOpenerRes(BaseModel):
    """그날 그 멘토 첫 진입 응답.

    first_today=True일 때만 프론트가 카드를 노출한다(하루 한 번). 재진입 시
    first_today=False지만 report는 동일하게 내려 '전체 리포트 보기'는 항상 가능.
    """

    first_today: bool
    opener: str
    report: DailyReportCard
