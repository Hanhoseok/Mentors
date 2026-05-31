"""기사 URL에서 풀 본문 + 대표 이미지 추출.

RSS feed(특히 Google News)는 본문 대신 짧은 스니펫만 줌. 그 짧은 텍스트를
LLM에 넘기면 요약 품질이 떨어지고 신뢰도 점수도 낮게 나옴.

이 모듈은:
  1. URL을 직접 HTTP fetch
  2. Google News interstitial이면 실 publisher URL로 second-hop
  3. trafilatura로 본문 추출 (실패 시 BeautifulSoup → regex strip fallback)
  4. 같은 페이지에서 og:image / twitter:image / first <img> 추출
  5. 보일러플레이트(광고·구독 안내·저작권 문구) 제거

mentors 컨벤션 적용:
  - 의존성: httpx (이미 있음), trafilatura (이 PR에서 추가), bs4/lxml (PR-3에서 추가)
  - googlenewsdecoder는 미사용 — HTML interstitial 파싱 fallback만 사용
  - core/exceptions 사용 안 함 — 추출 실패는 silent (None 반환)
  - 모든 외부 호출 async
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

try:
    import trafilatura
    _HAS_TRAFILATURA = True
except Exception:  # pragma: no cover
    trafilatura = None  # type: ignore[assignment]
    _HAS_TRAFILATURA = False

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment,misc]
    _HAS_BS4 = False

logger = logging.getLogger("content.extractor")


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# 추출된 본문이 이 길이 이상이어야 "real article body"로 인정.
MIN_ARTICLE_CHARS = 250

# 본문 저장 상한 — AI 처리기에 넘어가는 최대 길이.
MAX_ARTICLE_CHARS = 40000


class ContentExtractor:
    """URL → (본문, 이미지 URL) 추출 헬퍼.

    싱글톤으로 사용 (service.ContentService.__init__에서 생성). 내부 세마포어가
    동시 HTTP 호출을 제한해서 원격 서버를 과부하시키지 않음.
    """

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        max_concurrency: int = 6,
    ) -> None:
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        if not _HAS_TRAFILATURA:
            logger.warning(
                "trafilatura not installed — BS4 heuristic fallback만 사용"
            )

    async def extract(self, url: str) -> tuple[str | None, str | None, str | None]:
        """URL에서 본문·대표 이미지·최종 URL을 best-effort 추출.

        Args:
            url: 추출 대상 기사 URL. Google News redirect/interstitial 포함 OK —
                내부에서 second-hop으로 실 publisher URL을 따라감.

        Returns:
            `(body, image_url, resolved_url)` 튜플. 각 컴포넌트는 독립적으로
            성공/실패 가능 — 한 컴포넌트가 None이라고 나머지가 None은 아님.

            - **body** (`str | None`):
                보일러플레이트 제거된 본문. `MIN_ARTICLE_CHARS`(250) 미만이거나
                추출 실패면 None. `MAX_ARTICLE_CHARS`(40000)로 truncate.
            - **image_url** (`str | None`):
                og:image → twitter:image → 본문 첫 <img> 우선순위로 추출한 절대 URL.
                Google 도메인 이미지(로고·플레이스홀더)는 None으로 필터링.
                body 추출에 실패해도 이미지만 따로 반환할 수 있음 (best-effort).
            - **resolved_url** (`str | None`):
                HTTP redirect + Google News interstitial second-hop을 모두 따라간
                **최종 publisher URL**. 의미:

                  * `url`이 일반 publisher 링크면 보통 `url`과 동일 (308/301 등 일반
                    redirect만 적용된 정규화 형태).
                  * `url`이 Google News interstitial이면 실 publisher 도메인의 URL
                    (e.g. `https://reuters.com/...`).
                  * HTTP 단계에서 fetch 자체가 실패하면 None.

                **호출자 활용** (`ContentService._persist_articles`):
                `resolved_url`이 입력 `url`과 다르고 `canonicalize_url(resolved_url)`이
                입력 canonical과 다르면, publisher canonical로 2차 dedup 쿼리를 수행해
                같은 publisher 기사를 가리키는 다른 redirect URL이 이미 저장돼
                있는지 확인. 신규 저장이면 `canonical_url`을 publisher 값으로 기록.

        Notes:
            - 모든 실패 경로는 silent (예외 전파 없이 None 컴포넌트 반환).
              `core.exceptions`로 raise하지 않음 — 호출자는 raw fallback 사용.
            - 빈/whitespace `url`은 즉시 `(None, None, None)` 반환.
            - HTTP content-type이 html/xml이 아니면 본문은 None이지만
              `resolved_url`은 redirect 추적 결과를 그대로 반환.
        """
        if not url:
            return (None, None, None)

        async with self._semaphore:
            try:
                html, final_url = await self._fetch(url)
            except Exception as e:
                logger.warning(
                    "content.extractor.fetch_failed",
                    extra={"url": url[:200], "err": str(e)[:200]},
                )
                return (None, None, None)

            if not html:
                return (None, None, None)

            # Google News interstitial → 실 publisher URL로 second-hop
            if final_url and "news.google.com" in (urlparse(final_url).netloc or ""):
                resolved = self._find_google_news_target(html)
                if resolved and resolved != final_url:
                    try:
                        html2, final_url2 = await self._fetch(resolved)
                        if html2:
                            html, final_url = html2, final_url2
                    except Exception as e:
                        logger.debug(
                            "content.extractor.second_hop_failed",
                            extra={"url": resolved[:200], "err": str(e)[:200]},
                        )

            body = self._extract_body(html, final_url or url)
            image_url = self._extract_image(html, final_url or url)

            # Google 도메인 이미지(Google 로고 등) 필터링
            if image_url and self._is_google_image(image_url):
                logger.debug(
                    "content.extractor.google_image_filtered",
                    extra={"image_url": image_url[:200]},
                )
                image_url = None

            if not body:
                return (None, image_url, final_url)

            cleaned = self._postprocess(body)
            if len(cleaned) < MIN_ARTICLE_CHARS:
                return (None, image_url, final_url)
            return (cleaned[:MAX_ARTICLE_CHARS], image_url, final_url)

    # ------------------------------------------------------------------
    # HTTP fetch
    # ------------------------------------------------------------------

    async def _fetch(self, url: str) -> tuple[str | None, str | None]:
        """GET url. follow_redirects=True. returns (html, final_url)."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                logger.debug(
                    "content.extractor.http_error",
                    extra={"url": url[:200], "status": resp.status_code},
                )
                return None, str(resp.url)
            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype and "xml" not in ctype:
                return None, str(resp.url)
            return resp.text, str(resp.url)

    @staticmethod
    def _find_google_news_target(html: str) -> str | None:
        """Google News interstitial HTML에서 실 publisher URL 추출.

        Google News 가끔 interstitial 페이지를 줌. data-n-au 또는 meta refresh
        또는 일반 anchor에 실 URL이 들어있음.
        """
        if not html:
            return None
        m = re.search(r'data-n-au="(https?://[^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(
            r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=([^"\'>\s]+)',
            html,
            re.IGNORECASE,
        )
        if m:
            return m.group(1)
        m = re.search(
            r'<a[^>]+href="(https?://[^"]+)"[^>]+(?:rel=["\']?nofollow|target=)',
            html,
        )
        if m and "google.com" not in m.group(1):
            return m.group(1)
        return None

    # ------------------------------------------------------------------
    # Body extraction (trafilatura → BS4 → regex strip)
    # ------------------------------------------------------------------

    def _extract_body(self, html: str, url: str) -> str | None:
        if _HAS_TRAFILATURA:
            try:
                text = trafilatura.extract(
                    html,
                    url=url,
                    include_comments=False,
                    include_tables=False,
                    favor_precision=True,
                    no_fallback=False,
                )
                if text and len(text.strip()) >= MIN_ARTICLE_CHARS:
                    return text
            except Exception as e:
                logger.debug(
                    "content.extractor.trafilatura_failed",
                    extra={"url": url[:200], "err": str(e)[:200]},
                )

        if _HAS_BS4:
            try:
                return self._bs4_extract(html)
            except Exception as e:
                logger.debug(
                    "content.extractor.bs4_failed",
                    extra={"url": url[:200], "err": str(e)[:200]},
                )

        return self._strip_tags(html)

    @staticmethod
    def _bs4_extract(html: str) -> str | None:
        """heuristic: <article> 우선 → 가장 많은 <p>를 가진 <div>/<main>."""
        if not _HAS_BS4:
            return None
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(
            ["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]
        ):
            tag.decompose()

        article = soup.find("article")
        if article:
            text = article.get_text(separator="\n", strip=True)
            if len(text) >= MIN_ARTICLE_CHARS:
                return text

        best_text = ""
        for candidate in soup.find_all(["main", "div", "section"]):
            paragraphs = candidate.find_all("p")
            if len(paragraphs) < 3:
                continue
            text = "\n".join(p.get_text(" ", strip=True) for p in paragraphs)
            if len(text) > len(best_text):
                best_text = text

        if len(best_text) >= MIN_ARTICLE_CHARS:
            return best_text

        paragraphs = soup.find_all("p")
        text = "\n".join(p.get_text(" ", strip=True) for p in paragraphs)
        return text or None

    @staticmethod
    def _strip_tags(html: str) -> str | None:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    # ------------------------------------------------------------------
    # Image extraction (og:image → twitter:image → first <img>)
    # ------------------------------------------------------------------

    def _extract_image(self, html: str, base_url: str) -> str | None:
        if not html:
            return None

        for pattern in (
            r'<meta[^>]+property=["\']og:image(?::url)?["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::url)?["\']',
            r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
            r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
        ):
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                resolved = self._absolutize_image(m.group(1).strip(), base_url)
                if resolved:
                    return resolved

        if _HAS_BS4:
            try:
                soup = BeautifulSoup(html, "lxml")
                root = soup.find("article") or soup.body or soup
                for img in root.find_all("img"):
                    raw_src = (
                        img.get("src")
                        or img.get("data-src")
                        or img.get("data-lazy-src")
                    )
                    if not raw_src:
                        continue
                    # bs4가 src를 str | list[str] | None로 반환할 수 있음 — str로 정규화
                    src = raw_src if isinstance(raw_src, str) else str(raw_src)
                    w = self._safe_int(img.get("width"))
                    h = self._safe_int(img.get("height"))
                    if w and h and (w < 100 or h < 100):
                        continue
                    resolved = self._absolutize_image(src, base_url)
                    if resolved:
                        return resolved
            except Exception as e:
                logger.debug(
                    "content.extractor.img_bs4_failed",
                    extra={"url": base_url[:200], "err": str(e)[:200]},
                )
        return None

    @staticmethod
    def _safe_int(v: object) -> int | None:
        if v is None:
            return None
        try:
            return int(str(v).strip().rstrip("px"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_google_image(url: str) -> bool:
        """Google 도메인 이미지(Google 로고·플레이스홀더) 여부 확인."""
        if not url:
            return False
        try:
            netloc = urlparse(url).netloc.lower()
            return any(
                d in netloc
                for d in ("google.com", "gstatic.com", "googleapis.com", "googleusercontent.com")
            )
        except Exception:
            return False

    @staticmethod
    def _absolutize_image(src: str, base_url: str) -> str | None:
        if not src:
            return None
        src = src.strip()
        if " " in src:
            src = src.split(" ", 1)[0]
        if src.startswith("//"):
            scheme = urlparse(base_url).scheme or "https"
            return f"{scheme}:{src}"
        if src.startswith("http://") or src.startswith("https://"):
            return src
        if src.startswith(("data:", "javascript:")):
            return None
        if src.startswith("/"):
            parsed = urlparse(base_url)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}{src}"
        try:
            return urljoin(base_url, src)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    # 광고·구독·저작권 등 보일러플레이트 패턴 (한/영).
    _BOILERPLATE_RE = re.compile(
        r"(?i)\b("
        r"advertisement|sponsored\s+content|newsletter|subscribe(?:\s+now)?"
        r"|sign\s*up(?:\s+for)?|follow\s+us|share\s+this|read\s+more"
        r"|related\s+(?:stories|articles|coverage|posts)|recommended\s+for\s+you"
        r"|cookie(?:s)?\s+policy|privacy\s+policy|terms\s+of\s+(?:use|service)"
        r"|all\s+rights\s+reserved|©\s*\d{4}"
        r"|광고|구독\s*하기|뉴스레터|관련\s*기사|추천\s*기사|더\s*보기"
        r"|저작권자|무단\s*전재|재배포\s*금지|쿠키\s*정책|개인정보\s*처리방침"
        r")\b"
    )

    @classmethod
    def _postprocess(cls, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append("")
                continue
            if len(stripped) < 20 and ("http" in stripped or "©" in stripped):
                continue
            if len(stripped) < 200 and cls._BOILERPLATE_RE.search(stripped):
                continue
            lines.append(stripped)
        cleaned = "\n".join(lines).strip()
        return re.sub(r"\n{3,}", "\n\n", cleaned)


# 모듈 레벨 싱글톤 — service.ContentService가 사용
content_extractor = ContentExtractor()


__all__ = ["ContentExtractor", "content_extractor", "MIN_ARTICLE_CHARS", "MAX_ARTICLE_CHARS"]
