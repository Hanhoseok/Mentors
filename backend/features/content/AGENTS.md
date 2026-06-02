# content (5동) — AGENTS.md

> 콘텐츠 동 owner와 AI 에이전트가 매 작업 시작 시 read한다. 상위
> `backend/AGENTS.md`의 룰을 모두 따르며, 본 문서는 **content 동 specific 룰**.

---

## 1. 책임 범위

- 외부 뉴스 수집 (RSS, Finnhub) → dedup → 신뢰도 평가 → AI 번역·요약·전략 매핑
- RAG 인덱싱 (Chroma collection `content_news_kb`)
- 사용자 노출 피드 + 검색 + 스크랩
- 다른 동에 `ContentReader` 프로토콜로 데이터 제공 (`get_today_news_for_user`)

## 2. 핵심 파일

| 파일 | 역할 |
|---|---|
| `models.py` | SQLAlchemy 모델 (NewsArticle, MasterKeyword, KnowledgeChunk, Scrap) |
| `schemas.py` | Pydantic v2 (API 입출력 + 내부 DTO) |
| `pipeline_utils.py` | 순수 함수 (dedup, reliability, classifier) — 외부 호출 X |
| `collectors/` | Google News RSS, Finnhub. 콘텐츠 동 자체 사용 — 코어 래퍼 불필요 |
| `service.py` | 수집·AI·RAG 인덱싱 오케스트레이션 — singleton `content_service` |
| `read_service.py` | `ContentReader` 프로토콜 구현 (다른 동 접근점) |
| `router.py` | `/api/content/*` 사용자 노출 |
| `jobs.py` | `@interval` 스케줄러 (수집 10m, AI 5m, RAG 15m) |
| `handlers.py` | 이벤트 핸들러 (`ScrapAddedEvent`) — 멱등 필수 |

## 3. 자주 하는 작업

### 새 수집기 추가
1. `collectors/<name>.py`에 `BaseCollector` 상속
2. `collect(keyword, max_items)` 구현 (실패 시 예외 던져도 OK — `collect_safe`가 삼킴)
3. `collectors/__init__.py`에 등록
4. `service.py`의 `ContentService.__init__`에 인스턴스 추가

### 새 ContentReader 메서드 노출
1. `core/read_services/protocols.py`의 `ContentReader`에 시그니처 추가 PR (코어 owner 리뷰)
2. 본 동의 `read_service.py`에 구현 추가
3. 호출 동(예: daily_report)이 `from core.read_services import content_reader` 사용

### 새 멘토 전략 매칭 키워드
- `pipeline_utils._STRATEGY_HINTS`에 추가 (규칙 기반 1차)
- AI processor 프롬프트도 갱신 필요하면 `service._ai_for_article`의 system prompt에 추가

## 4. 금지 사항 (5동 specific)

- ❌ openai/anthropic SDK 직접 import — `from core.llm import llm` 사용
- ❌ chromadb 직접 사용 — `from core.vector_store import vector_store`
- ❌ raw SQL — async SQLAlchemy ORM만
- ❌ `get_today_news_for_user`에서 다른 동 테이블 직접 SELECT — `core.user_context` 사용
- ❌ 핸들러에서 event_id 멱등 가드 누락 — `_already_processed(event.event_id)` 체크 필수
- ❌ RSS/Finnhub 응답을 dedup 없이 그대로 저장 — `canonicalize_url` 필수

## 5. AI 응답 검증

뉴스 자체는 **사용자에게 자연어 응답을 만들지 않는다** (제목·요약은 LLM이 만들지만,
이건 콘텐츠 가공이지 대화 응답이 아님). 따라서:
- guardrail / hallucination / critic 파이프라인은 **본 동에서는 적용 불필요**
- 단, 콘텐츠 동이 생성한 summary를 멘토 채팅이 직접 자연어로 인용할 땐 그쪽
  파이프라인에서 검증 (학습 동의 책임)

## 6. 운영·모니터링

스케줄러 상태 확인:
- `content_collect` (10m): 새 기사 수집 카운트 로그
- `content_ai_process` (5m): pending → completed/failed 카운트
- `content_rag_index` (15m): Chroma upsert 카운트

장애 대응:
- LLM 다운 → `process_pending_ai`가 `failed` 상태로 남김. `ai_processing_status='failed'` 행을
  배치로 retry (Manual 트리거 endpoint 미구현 — 필요시 추가 PR)
- Chroma 다운 → `index_for_rag`가 다음 tick에 재시도. 데이터 손실 없음
- Redis 다운 → `event_bus.publish`가 silent fail. 핸들러는 멱등이라 미수신은 추후 재처리 시 자연 회복

## 7. PR 시 체크

- [ ] 수집기 추가 시 unit test 추가 (외부 호출은 `httpx.MockTransport`로 mock)
- [ ] `models.py` 변경 시 Alembic 마이그레이션 동반
- [ ] `read_service` 시그니처 변경 시 `core/read_services/protocols.py` PR 동반
- [ ] 새 event 발행 시 `core/contracts/events.py` PR 동반

## 8. 변경 이력

| 일자 | 변경 |
|---|---|
| 2026-05-24 | 최초 작성 (newspipeline 포팅 — 수집·신뢰도·RAG 인덱싱·스크랩) |
