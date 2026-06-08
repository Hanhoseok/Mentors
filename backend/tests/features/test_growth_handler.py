from types import SimpleNamespace

import pytest

from core.contracts import ConceptId, Tier, UserId
from core.jobs import scheduler
from features.growth.models import ConceptMastery
from features.growth.service import process_concept_mastered_event


class _ExecuteResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeSession:
    def __init__(self, mastered_ids: set[int]) -> None:
        self._mastered_ids = mastered_ids
        self._existing = False
        self.commits = 0

    async def execute(self, _stmt: object) -> _ExecuteResult:
        return _ExecuteResult(object() if self._existing else None)

    def add(self, obj: object) -> None:
        if isinstance(obj, ConceptMastery):
            self._mastered_ids.add(int(obj.concept_id))
            self._existing = True

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_process_concept_mastered_event_is_idempotent_for_duplicate_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mastered_ids = {101, 102, 103, 104, 105, 106, 107}
    fake_db = _FakeSession(mastered_ids)
    fake_state = SimpleNamespace(
        current_tier=Tier.T1.value,
        promotion_eligible_at=None,
        mastered_concepts=7,
        total_concepts=10,
        progress_percent=70,
    )
    published_events: list[object] = []
    pushed_payloads: list[dict[str, object]] = []
    scheduled_jobs: list[dict[str, object]] = []

    async def fake_ensure_state(*_args: object, **_kwargs: object) -> tuple[object, bool]:
        return fake_state, False

    async def fake_list_mastered(*_args: object, **_kwargs: object) -> set[int]:
        return set(mastered_ids)

    async def fake_publish(event: object) -> None:
        published_events.append(event)

    async def fake_push(*, user_id: UserId, title: str, body: str, data: dict[str, str]) -> int:
        pushed_payloads.append(
            {
                "user_id": user_id,
                "title": title,
                "body": body,
                "data": data,
            }
        )
        return 1

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
    monkeypatch.setattr("features.growth.service.push.send_to_user", fake_push)
    monkeypatch.setattr(scheduler, "add_job", fake_add_job)

    await process_concept_mastered_event(UserId(1), ConceptId(108), "evt_1", fake_db)
    await process_concept_mastered_event(UserId(1), ConceptId(108), "evt_1", fake_db)

    assert fake_state.progress_percent == 80
    assert fake_state.promotion_eligible_at is not None
    assert len(published_events) == 1
    assert pushed_payloads == []
    assert len(scheduled_jobs) == 1
    assert scheduled_jobs[0]["trigger"] == "date"
