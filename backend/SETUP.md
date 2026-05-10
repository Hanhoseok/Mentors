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
부팅: uv run uvicorn main:app --reload
```

---

**셋업이 끝나면 이 파일은 다시 안 본다.** 매일 보는 건 [AGENTS.md](AGENTS.md).
