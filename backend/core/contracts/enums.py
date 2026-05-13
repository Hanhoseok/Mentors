from enum import StrEnum


class Tier(StrEnum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    T5 = "T5"

    @property
    def next(self) -> "Tier | None":
        order = [Tier.T1, Tier.T2, Tier.T3, Tier.T4, Tier.T5]
        idx = order.index(self)
        return order[idx + 1] if idx + 1 < len(order) else None


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class MentorStrategy(StrEnum):
    """멘토에 내재된 투자전략 (도메인 사전 §3.2)."""

    VALUE = "value"
    GROWTH = "growth"
    DIVIDEND = "dividend"
    MOMENTUM = "momentum"


__all__ = ["MentorStrategy", "MessageRole", "Tier", "UserStatus"]
