from types import SimpleNamespace

import pytest

from core.contracts import Tier, UserId
from core.jobs import scheduler
from features.growth.catalog import list_promotion_questions
from features.growth.schemas import PromotionTestAnswerRequest, PromotionTestRequest
from features.growth.service import submit_promotion_test


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.executed: list[object] = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def execute(self, stmt: object) -> None:
        self.executed.append(stmt)
        return None

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_submit_promotion_test_schedules_unlock_reminder_after_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = _FakeSession()
    fake_state = SimpleNamespace(
        current_tier=Tier.T1.value,
        promotion_eligible_at=None,
        last_promotion_attempt_at=None,
        mastered_concepts=8,
        total_concepts=10,
        progress_percent=80,
    )
    published_events: list[object] = []
    scheduled_jobs: list[dict[str, object]] = []

    async def fake_ensure_state(*_args: object, **_kwargs: object) -> tuple[object, bool]:
        return fake_state, False

    async def fake_list_mastered(*_args: object, **_kwargs: object) -> set[int]:
        return {101, 102, 103, 104, 105, 106, 107, 108}

    async def fake_publish(event: object) -> None:
        published_events.append(event)

    def fake_add_job(func: object, trigger: str, **kwargs: object) -> None:
        scheduled_jobs.append(
            {
                "func": func,
                "trigger": trigger,
                "kwargs": kwargs,
            }
        )

    monkeypatch.setattr("features.growth.service._ensure_tier_state", fake_ensure_state)
    monkeypatch.setattr("features.growth.service._list_mastered_concept_ids", fake_list_mastered)
    monkeypatch.setattr("features.growth.service.event_bus.publish", fake_publish)
    monkeypatch.setattr(scheduler, "add_job", fake_add_job)

    answers = [
        PromotionTestAnswerRequest(
            question_id=question.id,
            choice_id=question.correct_choice_id,
        )
        for question in list_promotion_questions(Tier.T1)
    ]

    result = await submit_promotion_test(
        UserId(1),
        PromotionTestRequest(answers=answers),
        fake_db,  # type: ignore[arg-type]
    )

    assert result.passed is True
    assert result.current_tier == Tier.T2.value
    assert len(published_events) == 2
    assert len(scheduled_jobs) == 1
    assert scheduled_jobs[0]["trigger"] == "date"
