from core.llm.client import DEFAULT_GEMINI_MODEL
from core.llm.gateway import (
    DEFAULT_GEMINI_FALLBACK_MODEL,
    _google_chat_model_candidates,
    _is_google_high_demand_error,
)


class FakeGoogleError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def test_google_chat_model_candidates_use_flash_lite_fallback() -> None:
    assert _google_chat_model_candidates(DEFAULT_GEMINI_MODEL) == [
        DEFAULT_GEMINI_MODEL,
        DEFAULT_GEMINI_FALLBACK_MODEL,
    ]
    assert _google_chat_model_candidates(DEFAULT_GEMINI_FALLBACK_MODEL) == [
        DEFAULT_GEMINI_FALLBACK_MODEL
    ]


def test_google_high_demand_error_detection() -> None:
    assert _is_google_high_demand_error(FakeGoogleError("temporary", status_code=503))
    assert _is_google_high_demand_error(
        FakeGoogleError("503 UNAVAILABLE: This model is currently experiencing high demand")
    )
    assert not _is_google_high_demand_error(FakeGoogleError("401 invalid API key", status_code=401))
