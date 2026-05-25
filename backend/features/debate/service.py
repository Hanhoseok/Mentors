"""토론 생성 유스케이스 서비스.

router.py는 HTTP/SSE/DB 처리를 맡고, 이 모듈은 토론 생성 흐름을
mentor_ai.py에 위임한다.
"""

from __future__ import annotations

from core.ai_pipeline import RAGContext
from core.ai_pipeline.critic import CriticResult
from features.debate import mentor_ai
from features.debate.personas import DebatePersona

TurnSpec = mentor_ai.TurnSpec
DebateScriptTurn = mentor_ai.DebateScriptTurn
NewsEvidence = mentor_ai.NewsEvidence


def is_llm_ready() -> bool:
    return mentor_ai.is_llm_ready()


async def refine_topic(user_input: str) -> str | None:
    return await mentor_ai.refine_debate_topic(user_input)


async def generate_script(
    topic: str,
    turns: list[TurnSpec],
    context: RAGContext,
) -> dict[int, DebateScriptTurn] | None:
    return await mentor_ai.generate_debate_script(topic, turns, context)


async def generate_turn_answer(
    topic: str,
    persona: DebatePersona,
    turn_type: str,
    instruction: str,
    context: RAGContext,
    history: list[str],
) -> str:
    return await mentor_ai.generate_turn(
        topic,
        persona,
        turn_type,
        instruction,
        context,
        history,
    )


async def check_answer(
    answer: str,
    persona: DebatePersona,
    context: RAGContext,
) -> tuple[str, CriticResult | None]:
    return await mentor_ai.check_answer(answer, persona, context)


def fallback_turn(
    topic: str,
    persona: DebatePersona,
    turn_type: str,
    context: RAGContext,
    history: list[str],
) -> str:
    return mentor_ai.fallback_turn(topic, persona, turn_type, context, history)


extract_news_evidence = mentor_ai.extract_news_evidence
extract_news_summary = mentor_ai.extract_news_summary
is_low_signal_news = mentor_ai.is_low_signal_news
needs_turn_retry = mentor_ai.needs_turn_retry
parse_debate_script = mentor_ai.parse_debate_script
natural_news_reference = mentor_ai.natural_news_reference
summarize_news_title = mentor_ai.summarize_news_title
llm = mentor_ai.llm
