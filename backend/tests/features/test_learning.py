"""학습 동 단위 테스트 — 결정론적 로직만 (curriculum / personas / schemas).

DB·LLM·이벤트 버스 의존성 없음. SSE 스트리밍 및 라우터 통합 테스트는 별도.
"""

import pytest
from pydantic import ValidationError

from core.contracts import MentorStrategy, Tier
from core.exceptions import NotFoundError
from features.learning.curriculum import get_quiz, grade_quiz, list_quizzes_for_tier
from features.learning.personas import get_mentor_strategy, get_system_prompt
from features.learning.schemas import ChatStreamReq, SendMessageReq, SubmitQuizReq

# --- curriculum ---------------------------------------------------------------


@pytest.mark.parametrize(
    "concept_id, expected_name",
    [
        (101, "안전마진"),
        (102, "내재가치"),
        (103, "장기 투자 관점"),
        (104, "변동성과 리스크의 차이"),
        (105, "좋은 비즈니스의 질"),
    ],
)
def test_get_quiz_returns_catalogued_concept(concept_id: int, expected_name: str) -> None:
    quiz = get_quiz(concept_id)
    assert quiz.concept_id == concept_id
    assert quiz.concept_name == expected_name
    # 카탈로그 정합성: 모든 문항은 정확히 4지선다, 정답 인덱스가 옵션 범위 내
    assert len(quiz.options) == 4
    assert 0 <= quiz.correct_index < len(quiz.options)


def test_get_quiz_raises_not_found_for_unknown_concept() -> None:
    with pytest.raises(NotFoundError):
        get_quiz(999)


@pytest.mark.parametrize("concept_id", [101, 102, 103, 104, 105])
def test_grade_quiz_correct_index_returns_true(concept_id: int) -> None:
    quiz = get_quiz(concept_id)
    is_correct, explanation = grade_quiz(concept_id, quiz.correct_index)
    assert is_correct is True
    assert explanation  # 해설은 비어있지 않아야 함


def test_grade_quiz_wrong_index_returns_false_with_explanation() -> None:
    quiz = get_quiz(101)
    wrong_index = (quiz.correct_index + 1) % len(quiz.options)
    is_correct, explanation = grade_quiz(101, wrong_index)
    assert is_correct is False
    assert explanation == quiz.explanation


def test_grade_quiz_unknown_concept_raises() -> None:
    with pytest.raises(NotFoundError):
        grade_quiz(999, 0)


def test_t1_learning_quizzes_cover_the_full_growth_gate() -> None:
    expected_t1_concept_ids = [101, 102, 103, 104, 105]
    resolved_ids = [quiz.concept_id for quiz in list_quizzes_for_tier(Tier.T1)]

    assert resolved_ids == expected_t1_concept_ids
    assert len(resolved_ids) == 5


# --- personas -----------------------------------------------------------------


@pytest.mark.parametrize(
    "mentor_id, expected",
    [
        (1, MentorStrategy.VALUE),
        (2, MentorStrategy.GROWTH),
        (3, MentorStrategy.DIVIDEND),
        (4, MentorStrategy.MOMENTUM),
    ],
)
def test_mentor_id_maps_to_strategy(mentor_id: int, expected: MentorStrategy) -> None:
    assert get_mentor_strategy(mentor_id) == expected


def test_unknown_mentor_id_defaults_to_value() -> None:
    # 방어적 fallback — 알 수 없는 ID는 가치투자 페르소나
    assert get_mentor_strategy(999) == MentorStrategy.VALUE
    assert get_mentor_strategy(0) == MentorStrategy.VALUE


def test_each_strategy_returns_non_empty_system_prompt() -> None:
    prompts = [get_system_prompt(s) for s in MentorStrategy]
    # 모든 페르소나에 시스템 프롬프트가 있고
    assert all(p.strip() for p in prompts)
    # 네 페르소나의 프롬프트는 서로 달라야 한다 (= 페르소나가 실제로 분리되어 있음)
    assert len(set(prompts)) == len(prompts)


# --- schemas (Pydantic validation) --------------------------------------------


def test_send_message_rejects_empty_content() -> None:
    with pytest.raises(ValidationError):
        SendMessageReq(content="")


def test_send_message_rejects_overlong_content() -> None:
    with pytest.raises(ValidationError):
        SendMessageReq(content="x" * 2001)


def test_send_message_accepts_boundary_lengths() -> None:
    # 1자, 2000자 경계값 모두 허용
    SendMessageReq(content="a")
    SendMessageReq(content="a" * 2000)


def test_chat_stream_requires_both_session_id_and_content() -> None:
    with pytest.raises(ValidationError):
        ChatStreamReq(content="hello")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ChatStreamReq(session_id=1)  # type: ignore[call-arg]


def test_submit_quiz_accepts_int_indices() -> None:
    req = SubmitQuizReq(concept_id=1, answer_index=0)
    assert req.concept_id == 1
    assert req.answer_index == 0
