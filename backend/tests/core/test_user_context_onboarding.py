from types import SimpleNamespace

import pytest

from core.contracts import Tier, UserId
from core.user_context.service import UserContextService


@pytest.mark.asyncio
async def test_user_context_reads_onboarding_profile_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = UserContextService()

    async def fake_load_profile(_user_id: UserId) -> SimpleNamespace:
        return SimpleNamespace(
            current_tier="T2",
            interests_json='["value", "macro"]',
            selected_mentor_id=3,
        )

    monkeypatch.setattr(service, "_load_profile", fake_load_profile)

    assert await service.get_tier(UserId(1)) == Tier.T2
    assert await service.get_interests(UserId(1)) == ["value", "macro"]
    assert await service._get_selected_mentor(UserId(1)) == 3


@pytest.mark.asyncio
async def test_user_context_falls_back_when_profile_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = UserContextService()

    async def fake_load_profile(_user_id: UserId) -> None:
        return None

    monkeypatch.setattr(service, "_load_profile", fake_load_profile)

    assert await service.get_tier(UserId(1)) == Tier.T1
    assert await service.get_interests(UserId(1)) == []
    assert await service._get_selected_mentor(UserId(1)) is None
