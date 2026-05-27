# 토론(debate) 구현 정리

## 1. 이 문서의 목적

이 문서는 토론 모듈이 현재 코드에서 어떤 구조로 동작하는지 빠르게 파악하기 위한 정리입니다.

특히 아래 내용을 중심으로 설명합니다.

- 토론 기능의 API 흐름
- 멘토 페르소나가 어디서 정의되는가
- 뉴스/RAG/LLM 응답 생성이 어떤 순서로 이어지는가
- 토론 세션과 메시지가 어디에 저장되는가
- 마이그레이션과 환경변수에서 확인할 점

---

## 2. 관련 파일

### 백엔드 핵심 파일

- `backend/features/debate/router.py`
- `backend/features/debate/models.py`
- `backend/features/debate/personas.py`
- `backend/core/ai_pipeline/news_search.py`
- `backend/core/llm/client.py`
- `backend/core/config.py`
- `backend/migrations/versions/20260516_debate_sessions.py`
- `backend/tests/features/test_debate.py`

### 로컬 확인용 파일

- `backend/scripts/debate_smoke.py`

---

## 3. 토론 모듈이 관리하는 데이터

토론 모듈은 아래 2개 테이블을 사용합니다.

### 3.1 `debate_sessions`

사용자가 시작한 토론의 단위입니다.

- 사용자 ID
- 토론 주제
- 1번/2번 멘토 ID
- 상태값
- 오류 메시지
- 생성/완료 시각

### 3.2 `debate_messages`

토론 세션 안에서 생성된 멘토 발화입니다.

- 토론 세션 ID
- 발화 순서
- 발화 멘토 ID
- 발화 타입
- 본문
- critic 결과
- 생성 시각

`debate_session_id`와 `turn_index` 조합은 중복되지 않도록 unique 제약을 둡니다.

---

## 4. 엔드포인트

| 메서드·경로 | 역할 |
|---|---|
| `GET /api/debate/eligibility` | 현재 사용자가 토론 기능을 사용할 수 있는지 확인 |
| `GET /api/debate/personas` | 선택 가능한 토론 멘토 목록 조회 |
| `POST /api/debate/start` | 토론 세션 생성 |
| `GET /api/debate/{debate_session_id}/stream` | 토론 답변 SSE 스트리밍 |

토론 기능은 T2 이상 사용자에게 열립니다. T1 사용자는 `ForbiddenError`로 차단됩니다.

---

## 5. 멘토 페르소나

멘토 페르소나는 `features/debate/personas.py`에 정의되어 있습니다.

- `value`: 가치투자 멘토
- `momentum`: 모멘텀 멘토
- `growth`: 성장주 멘토
- `dividend`: 배당주 멘토

각 페르소나는 이름, 투자 관점, 말투, 시스템 규칙을 가집니다. 라우터는 요청으로 받은 `persona_a_id`, `persona_b_id`를 검증한 뒤 해당 페르소나를 사용합니다.

---

## 6. 토론 생성 흐름

### 6.1 세션 생성

1. 사용자가 `POST /api/debate/start`를 호출합니다.
2. 사용자 티어가 T2 이상인지 확인합니다.
3. 주제와 멘토 ID를 검증합니다.
4. `debate_sessions`에 세션을 저장합니다.
5. 클라이언트에 `stream_url`을 반환합니다.

### 6.2 스트리밍

1. 클라이언트가 `GET /api/debate/{id}/stream`을 호출합니다.
2. 이미 완료된 세션이면 저장된 메시지를 replay합니다.
3. 새 세션이면 토론 주제에서 키워드를 추출합니다.
4. RAG 문서와 뉴스 문서를 수집합니다.
5. 관련도 낮은 뉴스와 저품질 문서를 필터링합니다.
6. LLM에 3턴 토론 스크립트를 한 번에 요청합니다.
7. 파싱이 실패하거나 응답이 부족하면 로컬 fallback 발화를 사용합니다.
8. 각 발화를 SSE 이벤트로 전송하고 DB에 저장합니다.
9. 세션을 `completed`로 바꾸고 `DebateCompletedEvent`를 발행합니다.

---

## 7. 뉴스 검색과 근거 처리

뉴스 검색은 `core/ai_pipeline/news_search.py`가 담당합니다.

- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`이 있으면 Naver News Search API를 사용합니다.
- 키가 없으면 Google News RSS fallback을 사용합니다.
- Google News RSS 쿼리에는 기본적으로 `when:3d`를 붙여 최근 기사 위주로 검색합니다.

토론 라우터는 주제 키워드와 문서 제목/본문을 비교해 관련도가 낮은 문서를 제외합니다. LLM 프롬프트에는 기사 제목을 검색 단서로 제공하되, 핵심 문장에 없는 내용을 확정 사실처럼 말하지 않도록 제한합니다.

---

## 8. 시장 데이터 캐시와 주제 판별

토론 주제 판별은 먼저 `core/market_data`의 캐시를 조회합니다.

- `market_entities`에는 종목, 테마, 별칭, 섹터, 산업 정보를 저장합니다.
- `market_news_items`에는 주기적으로 수집한 관련 뉴스 메타데이터를 저장합니다.
- `MARKET_DATA_REFRESH_ENABLED=true`이면 APScheduler가 `MARKET_DATA_REFRESH_INTERVAL_MINUTES` 주기로 캐시 갱신 작업을 등록합니다.
- 캐시에 매칭되는 종목이 있으면 `stock`, 테마가 있으면 `theme`으로 먼저 정규화하고, 매칭이 없을 때만 기존 룰 기반 판별로 fallback합니다.

이 구조는 `팔란티어 전망`처럼 기존 하드코딩 목록에 없는 종목과 `우주테크 관련주 전망` 같은 신규 테마를 구분하기 위한 기반입니다.

---

## 9. LLM 응답 생성

기본 전략은 LLM 호출을 최소화하기 위해 3턴 토론 스크립트를 한 번에 생성하는 방식입니다.

생성 흐름은 다음 기준을 따릅니다.

- 주제 키워드와 뉴스 핵심 내용을 자연스럽게 연결합니다.
- 각 멘토의 투자 관점을 반영합니다.
- 반박과 재반박은 무조건 반대가 아니라 동의와 우려를 함께 다룹니다.
- 특정 종목의 직접 매수/매도 추천은 하지 않습니다.
- 파싱 실패 시 추가 LLM 호출을 반복하지 않고 로컬 fallback을 사용합니다.

---

## 10. 마이그레이션

토론 테이블은 `20260516_debate_sessions` 마이그레이션에서 생성됩니다.

현재 migration chain은 main의 최신 head 뒤에 debate migration이 붙도록 구성합니다.

```text
20260509_core_users
→ 20260510_core_devices
→ 20260519_learning_init_chat
→ 20260513_onboarding
→ 20260515_growth
→ 20260520_learning_quiz_attempts
→ 20260516_debate_sessions
```

작업 중 main에 새 마이그레이션이 머지되면 `down_revision`이 갈라지지 않았는지 확인해야 합니다.

확인 명령:

```bash
cd backend
uv run alembic heads
```

head가 여러 개 나오면 migration branch가 갈라진 것이므로, 일반적으로 새 기능 migration의 `down_revision`을 최신 main head로 조정하거나 merge revision을 추가해야 합니다.

---

## 10. 로컬 검증

토론 기능 관련 테스트:

```bash
cd backend
env UV_CACHE_DIR=/private/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/private/tmp/uv-python uv run pytest tests/features/test_debate.py tests/features/test_learning.py
```

LLM/API 호출 없이 주요 로직을 검증합니다.

실제 Gemini 응답까지 확인하려면 `scripts/debate_smoke.py`를 사용할 수 있습니다. 이 경우 Gemini와 뉴스 검색 호출이 발생할 수 있으므로 호출 횟수와 결과를 함께 확인해야 합니다.
