import pytest
from sqlalchemy.exc import ProgrammingError

from core.contracts import Tier, UserId
from features.learning.quizzes import recommend_tier_quiz_for_chat, submit_tier_quiz
from features.learning.tier_quizzes import get_tier_quiz


def _missing_progress_table_error() -> ProgrammingError:
    return ProgrammingError(
        "SELECT 1",
        {},
        Exception('relation "learning_quiz_progress" does not exist'),
    )


class _MissingProgressExecuteDb:
    def __init__(self) -> None:
        self.rolled_back = False

    async def execute(self, _stmt: object) -> object:
        raise _missing_progress_table_error()

    async def rollback(self) -> None:
        self.rolled_back = True


class _MissingProgressScalarDb:
    def __init__(self) -> None:
        self.rolled_back = False

    async def scalar(self, _stmt: object) -> object:
        raise _missing_progress_table_error()

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.asyncio
async def test_recommend_tier_quiz_for_chat_falls_back_when_progress_table_is_missing() -> None:
    db = _MissingProgressExecuteDb()
    quiz = await recommend_tier_quiz_for_chat(
        user_id=UserId(1),
        tier=Tier.T2,
        text="한 종목 비중은 어떻게 정해야 하나요?",
        db=db,  # type: ignore[arg-type]
    )

    assert quiz is not None
    assert quiz.question_id == "t2-f3"  # "한 종목 비중" → 개념 203 → t2-f3
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_submit_tier_quiz_still_grades_when_progress_table_is_missing() -> None:
    quiz = get_tier_quiz("t2-f5")
    db = _MissingProgressScalarDb()

    outcome = await submit_tier_quiz(
        user_id=UserId(1),
        question_id=quiz.question_id,
        answer_index=quiz.correct_index,
        db=db,  # type: ignore[arg-type]
    )

    assert outcome.correct is True
    assert outcome.explanation == quiz.explanation
    assert db.rolled_back is True
