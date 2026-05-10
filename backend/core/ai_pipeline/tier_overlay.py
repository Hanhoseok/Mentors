"""티어별 어휘 오버레이 (NFR-08, BR-04, 명세서 부록 8.1)."""

from core.contracts import Tier

_OVERLAY: dict[Tier, str] = {
    Tier.T1: (
        "기초 개념부터 풀어 설명한다. 전문용어가 등장하면 반드시 한 줄 정의를 함께 제공한다. "
        "비유와 일상 예시를 적극 사용한다."
    ),
    Tier.T2: (
        "기초 개념(PER 등)은 알고 있다고 가정한다. 산업 사이클·개념 간 연결을 함께 설명한다."
    ),
    Tier.T3: (
        "기업 해자, 복리 효과, 장기 보유 원칙 등 심화 개념을 자연스럽게 사용한다. "
        "기초 정의 반복은 생략한다."
    ),
    Tier.T4: (
        "현재 금리 환경·매크로 흐름에 따라 판단이 어떻게 달라지는지 시장 맥락을 적극 연계한다."
    ),
    Tier.T5: (
        "철학을 조합·응용하는 토론적 답변. 청자의 비판적 사고를 자극한다. "
        "닫힌 결론을 주지 않고 판단의 거울 역할을 한다."
    ),
}


class TierVocabularyOverlay:
    def apply(self, prompt: str, tier: Tier) -> str:
        instruction = _OVERLAY.get(tier, _OVERLAY[Tier.T1])
        return f"{prompt}\n\n[티어 {tier.value} 어휘 정책]\n{instruction}"


tier_overlay = TierVocabularyOverlay()

__all__ = ["TierVocabularyOverlay", "tier_overlay"]
