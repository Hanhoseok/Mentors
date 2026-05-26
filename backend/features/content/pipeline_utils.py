"""순수 함수 — 외부 호출 없음, 테스트 쉬움. newspipeline에서 포팅.

포함:
  - 본문 정제 (HTML strip, RSS metadata 감지)
  - URL 정규화
  - 중복 감지 (URL/title 기반)
  - 신뢰도 점수 계산
  - 경제 뉴스 분류
  - 멘토 전략 매핑 (AI processor와 무관한 규칙 기반 기본값)
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from core.contracts import MentorStrategy

# ---------------------------------------------------------------------------
# 텍스트 정제
# ---------------------------------------------------------------------------


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_RSS_HINTS = ("href=", "google.com", "<a ", "redirector", "<![CDATA[")


def strip_html(s: str | None) -> str:
    """HTML 태그 제거 + 공백 정규화."""
    if not s:
        return ""
    return _WHITESPACE_RE.sub(" ", _TAG_RE.sub(" ", s)).strip()


def looks_like_rss_metadata(s: str | None) -> bool:
    """본문이 RSS 메타데이터 스니펫인지 휴리스틱 판단."""
    if not s:
        return True
    text = s.lower()
    hits = sum(1 for hint in _RSS_HINTS if hint in text)
    return hits >= 2 or len(strip_html(s)) < 100


# ---------------------------------------------------------------------------
# URL 정규화 (중복 감지용)
# ---------------------------------------------------------------------------


_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "ref_src",
}


def canonicalize_url(url: str) -> str:
    """추적 파라미터 제거 + 호스트 lowercase. 중복 감지 키."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url

    params = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in _TRACKING_PARAMS
    ]
    cleaned_query = urllib.parse.urlencode(params)

    return urllib.parse.urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            parsed.params,
            cleaned_query,
            "",  # drop fragment
        )
    )


def title_fingerprint(title: str) -> str:
    """제목 정규화 → 중복 감지 보조 키."""
    normalized = re.sub(r"[^\w가-힣]+", " ", title.lower()).strip()
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 신뢰도 점수 (0~100)
# ---------------------------------------------------------------------------


# 출처별 기본 점수 (newspipeline에서 발췌·축약). 누락된 출처는 30점.
_SOURCE_BASE_SCORES: dict[str, int] = {
    "Reuters": 45, "Bloomberg": 45, "Financial Times": 45, "WSJ": 45,
    "AP": 40, "CNBC": 35, "Yahoo Finance": 30, "MarketWatch": 35,
    "Finnhub": 35, "SEC": 50,
    "연합뉴스": 40, "조선비즈": 35, "한국경제": 38, "매일경제": 38,
}


def reliability_score(
    *,
    source_name: str | None,
    content: str | None,
    published_at: datetime | None,
    title: str | None = None,
) -> tuple[int, str, str]:
    """4개 신호 합산. returns (score, level, reason)."""
    reasons: list[str] = []

    # 1. 출처 신뢰도 (0~50)
    source_score = _SOURCE_BASE_SCORES.get(source_name or "", 30)
    reasons.append(f"source={source_score}")

    # 2. 콘텐츠 품질 (0~5): 본문 길이 + RSS 메타데이터 페널티
    content_score = 0
    body = strip_html(content)
    if not looks_like_rss_metadata(content) and len(body) >= 400:
        content_score = 5
    elif len(body) >= 200:
        content_score = 3
    reasons.append(f"content={content_score}")

    # 3. 최신성 (0~10): 발행 시각 기준 24h→10, 72h→5, 그 이후 0
    now = datetime.now(timezone.utc)
    recency_score = 0
    if published_at is not None:
        pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
        age = now - pub
        if age <= timedelta(hours=24):
            recency_score = 10
        elif age <= timedelta(hours=72):
            recency_score = 5
    reasons.append(f"recency={recency_score}")

    # 4. 근거/데이터 (0~20): 본문에 숫자·% 등장 빈도 휴리스틱
    evidence_score = 0
    if body:
        digits = len(re.findall(r"\d", body))
        percents = body.count("%")
        if digits >= 30 or percents >= 3:
            evidence_score = 15
        elif digits >= 10:
            evidence_score = 10
    reasons.append(f"evidence={evidence_score}")

    # 5. 페널티 (clickbait 등)
    penalty = 0
    if title:
        lowered = title.lower()
        clickbait_markers = ["충격", "경악", "you won't believe", "shocking", "must-read"]
        if any(m in lowered for m in clickbait_markers):
            penalty -= 10
    reasons.append(f"penalty={penalty}")

    score = max(0, min(100, source_score + content_score + recency_score + evidence_score + penalty))
    level = _level_for(score)
    return score, level, " ".join(reasons)


def _level_for(score: int) -> str:
    if score >= 90:
        return "very_high"
    if score >= 70:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# 경제 뉴스 분류 (규칙 기반)
# ---------------------------------------------------------------------------


_ECONOMY_KEYWORDS = {
    "ko": [
        "주가", "주식", "증시", "코스피", "코스닥", "환율", "금리", "물가", "GDP",
        "실적", "매출", "영업이익", "투자", "공시", "IPO", "배당", "M&A", "인플레이션",
    ],
    "en": [
        "stock", "shares", "earnings", "revenue", "profit", "ipo", "dividend",
        "merger", "acquisition", "inflation", "interest rate", "gdp", "forex",
    ],
}


def is_economy(title: str, content: str | None, language: str = "en") -> bool:
    text = (title + " " + (content or "")).lower()
    keywords = _ECONOMY_KEYWORDS.get("ko" if language == "ko" else "en", [])
    return any(k.lower() in text for k in keywords)


# ---------------------------------------------------------------------------
# 멘토 전략 매핑 (규칙 기반 1차 추정 — AI processor가 덮어쓸 수 있음)
# ---------------------------------------------------------------------------


_STRATEGY_HINTS: dict[MentorStrategy, list[str]] = {
    MentorStrategy.VALUE: [
        "valuation", "p/e", "book value", "intrinsic", "undervalued", "가치주", "저PER",
        "PBR", "내재가치",
    ],
    MentorStrategy.GROWTH: [
        "growth", "expansion", "innovation", "guidance raised", "성장주", "고성장",
        "신사업", "매출 성장",
    ],
    MentorStrategy.DIVIDEND: [
        "dividend", "payout", "yield", "income", "배당", "배당수익률", "분배금",
    ],
    MentorStrategy.MOMENTUM: [
        "surge", "rally", "breakout", "momentum", "급등", "급락", "단타", "거래량 증가",
    ],
}


def classify_strategies(title: str, content: str | None) -> list[MentorStrategy]:
    """기사에 관련된 멘토 전략 추정. 0~여러 개 반환."""
    text = (title + " " + (content or "")).lower()
    hits: list[MentorStrategy] = []
    for strategy, hints in _STRATEGY_HINTS.items():
        if any(h.lower() in text for h in hints):
            hits.append(strategy)
    return hits


__all__ = [
    "canonicalize_url",
    "classify_strategies",
    "is_economy",
    "looks_like_rss_metadata",
    "reliability_score",
    "strip_html",
    "title_fingerprint",
]
