"""2동 — 학습 (멘토 채팅·개념퀴즈·기록).

핵심 책임:
- 멘토와의 1:1 실시간 투자 멘토링 (SSE 스트리밍, RAG 지식 검색, 어휘 수준 오버레이)
- 투자 핵심 개념 퀴즈 출제 및 채점
- 퀴즈 정답 시 ConceptMasteredEvent 발행 → 성장 동 게이지 상승 연계
- LearningReader 등록 → 일일 리포트가 진도순 커리큘럼 개념을 읽어 리포트를 정렬 (ADR-014)
"""

from core.read_services import register_learning_reader

from .read_service import LearningReadServiceImpl
from .router import router

register_learning_reader(LearningReadServiceImpl())

__all__ = ["router"]
