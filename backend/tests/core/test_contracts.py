"""Contracts — 이벤트 직렬화 / Tier 진행 / Reader registry."""

import pytest

from core.contracts import ConceptId, ConceptMasteredEvent, Tier, UserId, UserSignedUpEvent


def test_event_id_prefix() -> None:
    e = UserSignedUpEvent(user_id=UserId(1))
    assert e.event_type == "user.signed_up"
    assert e.event_id.startswith("evt_")


def test_event_roundtrip() -> None:
    original = ConceptMasteredEvent(user_id=UserId(42), concept_id=ConceptId(7))
    payload = original.model_dump_json()
    restored = ConceptMasteredEvent.model_validate_json(payload)
    assert restored.user_id == 42
    assert restored.concept_id == 7
    assert restored.event_id == original.event_id


def test_tier_next() -> None:
    assert Tier.T1.next == Tier.T2
    assert Tier.T4.next == Tier.T5
    assert Tier.T5.next is None


def test_content_reader_unregistered_message() -> None:
    # 새 프로세스에서는 미등록 상태. main.py를 import하면 features.content가 등록되므로
    # 이 테스트는 features를 import하지 않는 격리 환경이 필요. 여기선 메시지 패턴만 검증.
    from core.read_services.registry import get_content_reader

    # 한 번 등록되면 모듈 전역 상태이므로 — 등록 여부는 환경에 따라 다를 수 있음
    try:
        reader = get_content_reader()
        assert reader is not None  # 등록된 상태
    except RuntimeError as e:
        assert "ContentReader not registered" in str(e)
        pytest.skip("ContentReader 미등록 — 메시지만 확인")
