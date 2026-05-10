# AGENTS.md

> Mentors 백엔드의 동(棟) owner와 AI 코딩 에이전트가 **매 작업 시작 시 read하는 운영 룰**.
> 코어 인프라(`core/`)는 코어 owner가 단독 유지한다. 동 owner와 AI 에이전트는 본 문서를 진입점으로 삼는다.
> 본 문서가 진실의 원천이다. 수정 시 §12 변경 이력에 한 줄 추가.
>
> **레포를 처음 받았다면** → [SETUP.md](SETUP.md)를 먼저 1회 실행한 뒤 본 문서를 §1부터 읽는다.

---

## 1. 1분 요약

- **서비스**: Mentors — 2030 초보 투자자를 위한 AI 투자 멘토. "전략을 주는 게 아니라 전략이 태어날 환경을 제공"한다.
- **백엔드 형태**: Modular Monolith. FastAPI + PostgreSQL + Redis + Chroma + OpenAI/Anthropic + FCM.
- **6개 동 (`features/`)**: onboarding, learning, growth, debate, content, daily_report — 각 동에 owner 1명.
- **16 코어 모듈 (`core/`)**: 동들이 공유하는 공용 시설. 동 owner는 **수정 안 한다.** 변경이 필요하면 PR.
- **핵심 원칙 3개**:
  1. 자기 동 폴더만 수정한다. 다른 동을 직접 import하지 않는다.
  2. 옆 동의 데이터를 읽을 땐 코어를 통과한다 (`user_context` / `read_services`).
  3. 옆 동에 변경을 알릴 땐 `event_bus`로 발행한다 (fire-and-forget, 핸들러는 멱등).

이 3개를 어기지 않으면 6명이 동시에 PR을 올려도 머지 충돌이 거의 없다.

---

## 2. 디렉토리 = owner

```
mentors-backend/         # repo root
├── core/                # 동 owner는 직접 수정 금지 (PR 필수)
└── features/
    ├── onboarding/      # 1동 owner만 수정
    ├── learning/        # 2동 owner만 수정
    ├── growth/          # 3동 owner만 수정
    ├── debate/          # 4동 owner만 수정
    ├── content/         # 5동 owner만 수정
    └── daily_report/    # 6동 owner만 수정
```

다른 폴더의 파일을 수정하려는 충동이 들면 멈추고 PR로 분리한다.

---

## 3. Import 룰

### 절대 금지

```python
from features.learning.service import ...     # 다른 동 import 금지 (ADR-002)
from features.content.models import ...

import openai                                  # 외부 SDK 직접 사용 금지 (ADR-010)
import chromadb                                # → core/llm, core/vector_store 사용
from sqlalchemy import create_engine           # → core/db 사용

db.execute("SELECT * FROM users WHERE ...")    # raw SQL 금지 — ORM/Core만
```

### 권장 import

```python
from core.user_context import user_context                    # 사용자 상태
from core.read_services import content_reader                 # 다른 동 콘텐츠
from core.event_bus import event_bus                          # 이벤트 발행/구독
from core.contracts import ConceptMasteredEvent, Tier, UserId
from core.db import get_db, transaction                       # DB
from core.llm import llm                                      # chat / chat_stream / embed
from core.ai_pipeline import (                                # AI 품질 빌딩블록
    rag, guardrail, hallucination, citation, critic, tier_overlay,
)
from core.vector_store import vector_store
from core.cache import make_cache
from core.auth.dependencies import get_current_user
from core.exceptions import NotFoundError, BadRequestError, ConflictError
from core.jobs import cron, interval                          # 스케줄
from core.push import push                                    # FCM
```

### 한 가지 예외

토론 동은 **학습 동을 import하지 않는다.** 멘토 페르소나가 필요하면 `core/contracts`에 공용으로 등재하거나, 토론 동 자체에서 정의한다 (ADR-011).

---

## 4. 코딩 컨벤션

### 4.1 언어·프레임워크
- Python 3.12+
- FastAPI + 비동기 SQLAlchemy 2.x + Pydantic v2
- 타입 힌트는 모든 public 함수에 필수
- DB·외부 호출은 항상 `async def`

### 4.2 도구
- 포맷터: `ruff format` (라인 100자)
- 린터: `ruff check` (E, F, I, B, UP, ASYNC)
- 타입체커: `mypy --strict`
- pre-commit 통합

### 4.3 명명
- 파일·모듈: `snake_case.py`
- 클래스: `PascalCase`
- 함수·변수: `snake_case`
- 상수: `UPPER_SNAKE`
- 테스트: `test_<대상>.py`, 함수는 `test_<행위>_<기대결과>`

### 4.4 라우터 시그니처

```python
@router.post("/messages", response_model=MessageRes)
async def create_message(
    req: MessageReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageRes:
    ...
```

순서: `req` → 인증 → DB → 기타 의존성. 일관되게.

### 4.5 에러

```python
# OK
raise NotFoundError("멘토를 찾을 수 없습니다")

# 금지
raise HTTPException(status_code=404, ...)   # core/exceptions 사용
```

---

## 5. 자주 하는 작업 — Cookbook

### 5.1 사용자 상태 읽기

```python
from core.user_context import user_context
ctx = await user_context.get_for_mentor_chat(user_id)
# ctx.tier, ctx.interests, ctx.selected_mentor_id ...
```

새 use-case DTO가 필요하면 `core/user_context/dto.py`에 PR.

### 5.2 다른 동 콘텐츠 읽기

```python
from core.read_services import content_reader
news = await content_reader.get_today_news_for_user(user_id, top_k=3)
```

자기 동이 콘텐츠를 노출하려면 `features/<동>/read_service.py` 구현 후 `__init__.py`에서 등록.

### 5.3 이벤트 발행

```python
from core.event_bus import event_bus
from core.contracts import ConceptMasteredEvent

await event_bus.publish(ConceptMasteredEvent(
    user_id=user.id, concept_id=cid, occurred_at=datetime.utcnow(),
))
```

새 이벤트 타입은 `core/contracts/events.py` PR.

### 5.4 이벤트 구독

```python
# features/<동>/handlers.py
async def on_concept_mastered(event: ConceptMasteredEvent) -> None:
    # 멱등 필수: event.event_id를 처리 기록 테이블에 UNIQUE 저장
    ...

# features/<동>/__init__.py
from core.event_bus import event_bus
from core.contracts import ConceptMasteredEvent
from .handlers import on_concept_mastered
event_bus.subscribe(ConceptMasteredEvent, on_concept_mastered)
```

### 5.5 LLM 호출 (단발)

```python
from core.llm import llm
res = await llm.chat([
    Message(role=MessageRole.SYSTEM, content="너는 가치투자 멘토야"),
    Message(role=MessageRole.USER, content=user_input),
])
```

### 5.6 LLM 스트리밍 (멘토 채팅·토론)

```python
from sse_starlette.sse import EventSourceResponse
from core.llm import llm

async def event_stream(messages):
    async for chunk in llm.chat_stream(messages=messages):
        yield {"event": "delta", "data": chunk.model_dump_json()}

@router.post("/chat/stream")
async def chat_stream(req: ChatReq, user=Depends(get_current_user)):
    return EventSourceResponse(event_stream(messages))
```

전체 패턴(가드레일 → RAG → 스트리밍 → 환각/critic 후처리)은 §5.12 참조 + 시범 PR `features/daily_report/service.py` 참고.

### 5.7 스케줄 작업

```python
# features/<동>/jobs.py
from core.jobs import cron
from core.event_bus import event_bus

@cron("0 8 * * *", id="daily_report_dispatch")
async def dispatch():
    user_ids = await get_active_user_ids()
    for uid in user_ids:
        await event_bus.publish(DailyReportRequestedEvent(user_id=uid, ...))

# features/<동>/__init__.py
from . import jobs   # noqa: F401  (등록 트리거)
```

스케줄 트리거 → fan-out 발행 → 핸들러 멱등 처리. 직접 fan-out 큐를 굴리지 않는다.

### 5.8 푸시 알림

```python
from core.push import push
await push.send_to_user(
    user_id=uid,
    title="...",
    body="...",
    data={"deeplink": "mentors://..."},
)
```

알림 페이로드에 PII·금융 정보 금지. `user_id`·`deeplink`만.

### 5.9 마이그레이션

파일명: `migrations/versions/YYYYMMDD_<owner>_<설명>.py`
같은 날 충돌 시 시간 suffix: `20260514_1430_learning_*.py`

```bash
alembic revision --autogenerate -m "learning: create chat_messages"
# 생성된 파일명을 컨벤션에 맞게 rename
```

다른 owner의 PR이 먼저 머지되면 자기 PR의 `down_revision`을 새 head로 수정해야 할 수 있다 — 코어 owner와 협의.

### 5.10 트랜잭션

```python
from core.db import transaction

async with transaction() as db:
    # commit 자동, 예외 시 rollback
    ...
```

여러 동에 걸친 작업: 자기 동 트랜잭션 + 이벤트 발행 (eventually consistent). 즉시 일관성이 필요한 케이스는 코어 owner와 의논.

### 5.11 캐시

```python
from core.cache import make_cache
cache = make_cache("learning")   # 네임스페이스 분리
await cache.set(f"chat:{cid}", value, ttl=300)
```

### 5.12 RAG·환각 검출 한 줄 패턴

```python
from core.ai_pipeline import rag, guardrail, hallucination, citation, critic, tier_overlay

g = guardrail.check_input(user_msg)
if not g.ok:
    raise BadRequestError(g.reason)

ctx = await rag.retrieve(query=user_msg, collection="<동>_kb")
prompt = tier_overlay.apply(build_prompt(...), tier=user_ctx.tier)
# llm.chat_stream(...) 후 hallucination → critic → citation 후처리
```

---

## 6. 자기 동에 추가하는 표준 절차

### 6.1 새 테이블
1. `features/<동>/models.py`에 SQLAlchemy 모델
2. `alembic revision --autogenerate -m "..."` (네이밍 컨벤션 준수)
3. 자기 동 외 import 안 함. 다른 동이 데이터 필요하면 `read_service`로 노출

### 6.2 새 이벤트
1. `core/contracts/events.py`에 모델 추가 (PR)
2. 코어 owner 1차 리뷰 + 영향 동 알림
3. 머지 후 발행

### 6.3 새 read_service 메서드
1. `core/read_services/protocols.py` Protocol에 시그니처 추가 (PR)
2. 자기 동(`features/<동>/read_service.py`)에 구현 추가
3. 호출 동에서 `from core.read_services import <reader>` 사용

### 6.4 새 use-case 컨텍스트
1. `core/user_context/dto.py`에 DTO 추가 PR
2. 코어 owner가 service 메서드 구현 (여러 동 데이터 조립이라)

### 6.5 새 라우터
- 경로 prefix: `/api/<동명>/`
- 인증 필요: `Depends(get_current_user)`
- 응답: `response_model` 명시
- OpenAPI 태그: 동 이름

---

## 7. 금지 사항 (BR·NFR 정렬)

| 금지 | 이유 |
|---|---|
| 종목 매수/매도 추천 응답 | BR-05 (금융소비자보호법) — `PromptGuardrail`로 차단 |
| LLM 응답을 그대로 반환 (RAG 컨텍스트 검증 없이) | NFR-04 — `HallucinationDetector` 통과 필수 |
| 페르소나 이탈 응답 (가치투자 멘토가 단타 코칭 등) | NFR-06, BR-07 — `CriticFilter` 통과 필수 |
| 이메일·이름 직접 로그 | 보안 — `user_id`만 |
| 비밀번호 저장 | 사용 안 함 (Google OAuth만) |
| `.env` 커밋 | `.gitignore` 필수 |
| `--no-verify` 푸시·`main` 강제 푸시 | 금지 |
| 다른 동의 테이블 직접 SELECT | ADR-002, ADR-003 위반 |

---

## 8. 테스트

### 8.1 종류
- **Unit**: service 로직 (mock 사용) — `tests/features/<동>/`
- **Integration**: 라우터 → DB — 테스트 DB 사용
- **Contract**: 이벤트 형식 검증 — contracts 변경 시 자동 트리거

### 8.2 fixture

```python
from tests.fixtures import test_user, fake_event_bus, mock_llm, mock_user_context
```

- 외부 호출(LLM, FCM, OAuth)은 mock
- DB는 docker-compose 테스트 인스턴스 사용

### 8.3 작성 룰
- 새 라우터는 happy path 1개 + 인증 실패 1개 + 도메인 예외 1개 최소
- 새 이벤트 핸들러는 멱등성 테스트 1개 (같은 event_id 두 번 → 부작용 1회)

---

## 9. PR 컨벤션

### 9.1 브랜치
`<동명>/<짧은-설명>` — 예: `learning/concept-quiz-trigger`

### 9.2 PR 제목
`feat(<동>): <설명>` / `fix(<동>): ...` / `chore(<동>): ...`
contracts 변경 시: `contracts: <설명>` (모든 동 owner 알림)

### 9.3 PR 본문
- 무엇이 바뀌었나 (1~3줄)
- 왜 바뀌었나 (FR/UC/NFR/BR ID 인용)
- 영향받는 동
- 테스트 결과 요약

### 9.4 리뷰
- 같은 동 변경: 코어 owner 또는 다른 owner 1명
- `core/` 변경: 코어 owner + 영향 동 owner
- `core/contracts/` 변경: 코어 owner + 영향 동 owner 전원

---

## 10. AI 코딩 에이전트용 추가 지시

### 10.1 에이전트가 멈춰야 할 때
- 다른 동(`features/<다른동>/`) 파일을 수정하려는 충동 → 멈추고 owner에게 PR 제안
- `core/`를 수정하려는 충동 → 멈추고 사용자 확인
- 외부 SDK(`openai`, `chromadb`, `httpx` 등)를 직접 import하려는 충동 → 멈추고 코어 래퍼 사용
- 새로운 의존성을 추가하려는 충동 → `pyproject.toml`을 보고 사용자 확인

### 10.2 에이전트가 헷갈릴 때
1. 코어 인터페이스 시그니처 → `core/<모듈>/__init__.py` 또는 해당 `.py` 직접 read
2. 이벤트 이름·필드 → `core/contracts/events.py` 직접 read
3. 다른 동의 read_service 메서드 → `core/read_services/protocols.py` 직접 read
4. 같은 일을 코어가 이미 하고 있는지 → `core/`를 grep 먼저, 동에 새로 만들기 전에
5. 동이 어떻게 짜여야 하는지 모범 사례 → `features/daily_report/` 정독

### 10.3 에이전트가 절대 하지 말 것
- 임의의 라이브러리 추가 (`pip install ...`) — 사용자 확인 필수
- `migrations/versions/`의 기존 파일 수정
- `.env` 파일에 실제 값 작성
- 비밀키·API 키를 코드·로그·테스트에 하드코딩
- 사용자 PII를 새 테이블에 추가 (꼭 필요하면 사용자 확인)
- `git push --force`, `git reset --hard`, `git rebase -i`

### 10.4 에이전트가 매 작업 시작 전 read할 파일
1. `AGENTS.md` (이 파일)
2. `features/<자기 동>/AGENTS.md` (있으면 — 동 specific 룰)
3. `core/contracts/{events,enums,ids}.py`
4. `core/read_services/protocols.py`

---

## 11. 셀프 체크 (PR 올리기 전)

- [ ] 다른 동 폴더는 건드리지 않았다
- [ ] 외부 SDK를 직접 import하지 않았다
- [ ] raw SQL 문자열을 쓰지 않았다
- [ ] 이벤트 핸들러는 멱등하다 (event_id UNIQUE 처리)
- [ ] 사용자에게 노출되는 투자 관련 자연어 응답은 guardrail → RAG → hallucination → critic → citation 파이프라인을 반드시 통과한다. 내부 분류·요약 작업은 필요 시 예외 가능하되, 사용자 노출 전 검증 규칙은 동일하다.
- [ ] 비밀 정보·PII가 로그에 안 찍힌다
- [ ] 마이그레이션 파일명이 `YYYYMMDD_<owner>_*.py` 컨벤션
- [ ] `ruff format && ruff check && mypy` 통과
- [ ] 새 라우터는 최소 3개 테스트 (happy / unauth / domain error)

---

## 12. 변경 이력

> **규칙**: AGENTS.md를 수정하는 PR마다 AI 에이전트가 본 표 맨 아래에 한 줄 추가한다.
> 형식: `| YYYY-MM-DD | 한 줄 변경 요약 (PR #번호) |`. 오타·포맷만 고친 경우는 생략 가능.
> 큰 변경(섹션 신설·삭제·룰 추가)은 상단 안내문에서도 짧게 언급.

| 일자 | 변경 |
|---|---|
| 2026-05-09 | 최초 작성 (코어인프라_설계명세서 v1.1과 정렬) |
| 2026-05-10 | §0 셋업 섹션을 SETUP.md로 분리 / 상단 시점 표현(1주차·2주차) 일반화 / §12 자동 갱신 규칙 추가 |
| 2026-05-11 | docs/ 참조 4곳 제거 — 본 문서가 단일 진실의 원천 (코드 직접 read 권장). docs/ 폴더는 그대로 유지 (비상시 reference) |
