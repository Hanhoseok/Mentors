# SETUP.md — 첫 셋업

> **언제 사용**: 이 레포를 처음 받은 직후 1회. 그 후로는 안 본다.
> **누가 사용**: 사람 또는 AI 코딩 에이전트 (둘 다 같은 절차).
> **AI 에이전트에게**: 사용자에게 묻지 않고 순서대로 실행해도 된다. 각 단계는 graceful — 실패해도 다음 진행.

---

## Step 1 — 의존성 설치 (필수)
```bash
uv sync
```
실패 시 → uv 미설치. 사용자에게 https://docs.astral.sh/uv/ 안내.

## Step 2 — `.env` 생성 (필수, idempotent)
```powershell
# Windows
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```
```bash
# macOS/Linux
[ ! -f .env ] && cp .env.example .env
```
`.env`에는 placeholder만 들어 있다. 실제 키(`JWT_SECRET`, `OPENAI_API_KEY`, `GOOGLE_CLIENT_*` 등)는 사용자가 직접 채워야 한다. **키 없이도 앱은 부팅된다 — 해당 기능만 비활성화된다.**

## Step 3 — Docker 컨테이너 (선택)
```bash
docker compose up -d
```
Docker Desktop이 꺼져 있으면 실패 → 사용자에게 "Docker Desktop을 켜고 `docker compose up -d` 다시 실행" 안내 후 다음 단계 건너뛰기.

## Step 4 — DB 마이그레이션 (Step 3 성공 시)
```bash
uv run alembic upgrade head
```
DB 미실행 시 실패 → 건너뛰기 (Step 5·6은 그대로 진행 가능).

## Step 5 — 정적 검증 (필수, 항상 통과해야 함)
```bash
uv run ruff format .
uv run ruff check .
uv run mypy .
uv run pytest -q
```
**기준선** (1주차 완료 시점):
- `ruff check`: All passed
- `mypy --strict`: 79 files, 0 issues
- `pytest`: 14 passed

이 기준선이 무너지면 셋업이 잘못된 것 — 사용자에게 보고.

## Step 6 — 사용자에게 보고
다음 형식의 메시지를 출력:
```
✅ 셋업 완료
  · 의존성: 설치됨
  · 환경변수: .env 생성됨 (실제 키는 사용자가 채워야 함)
  · 컨테이너: <success|skipped — Docker Desktop 필요>
  · DB: <ready|pending>
  · 정적 검증: ruff/mypy/pytest 모두 통과

다음 단계:
  1. AGENTS.md 정독 (매 작업 시작 시 read하는 운영 룰)
  2. 시범 PR 코드 정독: features/daily_report/
  3. 자기 동 폴더(features/<자기-동>/) 첫 작업 시작
부팅 (Linux/Mac): uv run uvicorn main:app --reload
부팅 (Windows):   uv run python dev_server.py   ← Windows는 wrapper 필수, 아래 부록 참고
```

---

## 부록 — Windows 개발 환경 함정 (필독)

Windows + Docker Desktop 조합에서 발생하는 두 가지 트랩과 그 우회법. macOS/Linux는 영향 없음.

### 1. `localhost` → IPv6 우선 → 컨테이너 도달 실패

Windows는 `localhost`를 IPv6 `::1`로 먼저 resolve하지만, Docker Desktop의 컨테이너는 IPv4 `127.0.0.1`에만 바인딩됨. 결과: TCP 연결 reset, "connection was closed in the middle of operation" 류 에러.

**해결**: `.env`에 호스트값을 **`127.0.0.1`로 명시**. `.env.example`은 이미 그렇게 설정됨 — 복사만 하면 됨. Linux/Mac에서도 안전.

### 2. `psycopg` (async) ↔ `ProactorEventLoop` 비호환

Windows의 기본 asyncio 이벤트 루프는 ProactorEventLoop인데, `psycopg` async는 **명시적으로 SelectorEventLoop만 지원**. uvicorn cli는 OS 기본 루프를 따라가서 ProactorEventLoop을 만나면 즉시 실패.

**해결**: `uvicorn main:app` 대신 **`uv run python dev_server.py`** 사용. `dev_server.py`가 `asyncio.run(loop_factory=...)`로 SelectorEventLoop을 강제하고 그 안에서 uvicorn을 띄움. Linux/Mac에선 그냥 평소대로 `uvicorn main:app` 써도 됨 (dev_server.py도 OS 분기로 동일 동작).

### 3. dev token (OAuth 우회)

`ENV=dev`일 때 활성화되는 직접 토큰 발급 엔드포인트:
```
POST /auth/dev-token
{ "email": "me@test.com", "nickname": "선택" }   # 둘 다 옵션 — 비우면 dev+<uuid>@local.test 자동 생성
→ { "access_token": "...", "expires_in": 86400, "user": { ... }, "created": true }
```
브라우저 OAuth 거치지 않고 smoke client/프론트 dev 화면/통합 테스트에서 사용. 운영(`ENV=prod`)에선 403.

### 4. smoke client (`_smoke/index.html`)

`ENV=dev`에서 `http://127.0.0.1:8000/_smoke/`로 서빙됨 (FastAPI static mount). 채팅·퀴즈·커리큘럼을 같은 origin에서 시각 검증 가능. 별도 빌드 불필요.

---

**셋업이 끝나면 이 파일은 다시 안 본다.** 매일 보는 건 [AGENTS.md](AGENTS.md).
