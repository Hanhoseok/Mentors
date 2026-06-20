from collections import Counter

from core.contracts import Tier
from features.learning.concept_detector import recommend_quiz_for_text
from features.learning.tier_quizzes import (
    get_tier_quiz,
    get_tier_quiz_by_concept_index,
    list_tier_quizzes,
)


def test_each_tier_has_ten_follow_up_quizzes_one_per_concept() -> None:
    for tier in Tier:
        quizzes = list_tier_quizzes(tier)
        assert len(quizzes) == 10
        concept_counts = Counter(quiz.concept_id for quiz in quizzes)
        assert len(concept_counts) == 10  # 티어당 개념 10개
        assert all(count == 1 for count in concept_counts.values())  # 개념당 1문항


def test_get_tier_quiz_by_concept_index_returns_expected_quiz() -> None:
    quiz = get_tier_quiz_by_concept_index(101, 0)

    assert quiz.question_id == "t1-f1"
    assert quiz.concept_id == 101
    assert quiz.quiz_index == 0


def test_recommend_quiz_for_text_uses_current_tier_keywords() -> None:
    quiz = recommend_quiz_for_text(Tier.T1, "안전마진이 왜 중요한가요?", set())

    assert quiz is not None
    assert quiz.question_id == "t1-f1"


def test_recommend_quiz_for_text_skips_solved_question_and_moves_to_next() -> None:
    # 개념당 문항이 1개이므로, 상위 매칭 개념(안전마진=101)의 퀴즈가 이미 풀렸으면
    # 다음으로 매칭된 개념(복리=106)의 퀴즈로 넘어간다.
    quiz = recommend_quiz_for_text(Tier.T1, "안전마진 복리", {"t1-f1"})

    assert quiz is not None
    assert quiz.question_id == "t1-f6"
    assert quiz.concept_id == 106


def test_get_tier_quiz_returns_non_empty_korean_content() -> None:
    quiz = get_tier_quiz("t4-f3")

    assert quiz.question
    assert quiz.explanation
    assert len(quiz.options) == 4
