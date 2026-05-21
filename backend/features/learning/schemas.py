"""학습 동 Pydantic 스키마 — 요청/응답 모델."""

from datetime import datetime

from pydantic import BaseModel, Field


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
    concept_id: int = Field(..., description="투자 개념 ID")
    answer_index: int = Field(..., description="선택한 보기 인덱스 (0~3)")


class QuizOption(BaseModel):
    index: int
    text: str


class QuizRes(BaseModel):
    concept_id: int
    concept_name: str
    question: str
    options: list[QuizOption]


class TierQuizCatalogRes(BaseModel):
    tier: str
    quizzes: list[QuizRes]


class SubmitQuizRes(BaseModel):
    correct: bool
    explanation: str
