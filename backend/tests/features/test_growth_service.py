import math

import pytest
from sqlalchemy.exc import IntegrityError

from core.contracts import Tier, UserId
from features.growth.catalog import list_concepts_for_tier, list_promotion_questions
from features.growth.models import TierState
from features.growth.service import (
    _ensure_tier_state,
    apply_concept_mastery,
    compute_progress,
    get_next_unlock_codes,
    get_unlocked_feature_codes,
    grade_promotion_test,
)

# 기대값은 카탈로그(catalog.py / promotion_questions.toml)에서 파생한다.
# 개념/문항 수가 바뀌어도 테스트가 함께 따라가도록 하드코딩 ID를 쓰지 않는다.


def _answers_with_correct(tier: Tier, num_correct: int) -> dict[str, str]:
    """승급시험 답안을 만든다 — 앞 num_correct개만 정답, 나머지는 일부러 오답."""
    answers: dict[str, str] = {}
    for i, question in enumerate(list_promotion_questions(tier)):
        if i < num_correct:
            answers[question.id] = question.correct_choice_id
        else:
            answers[question.id] = next(
                c.id for c in question.choices if c.id != question.correct_choice_id
            )
    return answers


def test_compute_progress_marks_eligible_at_eighty_percent() -> None:
    concepts = list_concepts_for_tier(Tier.T1)
    total = len(concepts)
    take = math.ceil(total * 0.8)  # 80% 도달에 필요한 최소 개수
    mastered_ids = {c.id for c in concepts[:take]}

    snapshot = compute_progress(Tier.T1, mastered_ids)

    assert snapshot.total_concepts == total
    assert snapshot.mastered_concepts == take
    assert snapshot.progress_percent == int(take / total * 100)
    assert snapshot.progress_percent >= 80
    assert snapshot.eligible_for_promotion is True


def test_apply_concept_mastery_is_idempotent_for_duplicate_concept() -> None:
    concepts = list_concepts_for_tier(Tier.T2)
    base_ids = {c.id for c in concepts[:4]}
    target_id = concepts[4].id

    once = apply_concept_mastery(Tier.T2, base_ids, target_id)
    twice = apply_concept_mastery(Tier.T2, once.mastered_concept_ids, target_id)

    assert once.mastered_concepts == 5
    assert twice.mastered_concepts == 5  # 같은 개념 재숙달은 카운트 증가 없음
    assert once.progress_percent == twice.progress_percent


def test_grade_promotion_test_passes_at_eighty_percent() -> None:
    total = len(list_promotion_questions(Tier.T1))
    num_correct = (total * 80) // 100  # 80% 정답

    grade = grade_promotion_test(Tier.T1, _answers_with_correct(Tier.T1, num_correct))

    assert grade.total_questions == total
    assert grade.correct_answers == num_correct
    assert grade.score_percent == int(num_correct / total * 100)
    assert grade.score_percent >= 80
    assert grade.passed is True


def test_grade_promotion_test_fails_below_eighty_percent() -> None:
    total = len(list_promotion_questions(Tier.T2))
    num_correct = (total * 60) // 100  # 60% 정답 → 불합격

    grade = grade_promotion_test(Tier.T2, _answers_with_correct(Tier.T2, num_correct))

    assert grade.correct_answers == num_correct
    assert grade.score_percent < 80
    assert grade.passed is False


def test_get_unlocked_feature_codes_unlocks_debate_and_extra_mentors() -> None:
    assert get_unlocked_feature_codes(Tier.T1) == []
    assert get_unlocked_feature_codes(Tier.T2) == ["debate_arena"]
    assert get_unlocked_feature_codes(Tier.T3) == ["debate_arena", "extra_mentors"]
    assert get_next_unlock_codes(Tier.T1) == ["debate_arena"]
    assert get_next_unlock_codes(Tier.T2) == ["extra_mentors"]


def test_grade_promotion_test_requires_complete_answer_set() -> None:
    # 실제 문항 답안에서 하나를 빼면 '전체 답변 필요' 검증에 걸려야 한다.
    answers = _answers_with_correct(Tier.T1, num_correct=0)
    answers.pop(next(iter(answers)))
    with pytest.raises(ValueError):
        grade_promotion_test(Tier.T1, answers)


@pytest.mark.asyncio
async def test_ensure_tier_state_recovers_from_concurrent_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted_state = TierState(
        user_id=999,
        current_tier=Tier.T1.value,
        mastered_concepts=0,
        total_concepts=5,
        progress_percent=0,
    )

    class _FakeSession:
        def __init__(self) -> None:
            self.rollback_count = 0
            self.state: TierState | None = None

        async def get(self, _model: object, _pk: int) -> TierState | None:
            return self.state

        def add(self, _obj: object) -> None:
            return None

        async def flush(self) -> None:
            raise IntegrityError("insert", {}, Exception("duplicate"))

        async def rollback(self) -> None:
            self.rollback_count += 1
            self.state = persisted_state

    async def fake_get_tier(_user_id: UserId) -> Tier:
        return Tier.T1

    monkeypatch.setattr("features.growth.service.user_context.get_tier", fake_get_tier)

    fake_db = _FakeSession()
    state, created = await _ensure_tier_state(fake_db, UserId(999))

    assert created is False
    assert state is persisted_state
    assert fake_db.rollback_count == 1
