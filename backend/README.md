# Mentors Backend

2030 초보 투자자를 위한 AI 투자 멘토 서비스의 백엔드.

> **첫 셋업 (1회)**: [SETUP.md](SETUP.md) — 사람·AI 에이전트 모두 같은 절차. AI에게 "SETUP.md 따라 셋업해줘" 한 줄이면 끝.
> **매 작업 시작 시 read**: [AGENTS.md](AGENTS.md) — Import 룰 · cookbook · PR 컨벤션.
> **설계 자료**: [docs/](docs/) — 명세서·모듈 다이어그램·인수인계서·시각자료.

---

## 5분 셋업 (사람용)

### 1. 사전 요구
- Python 3.12+ (uv가 자동 설치)
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop (PostgreSQL · Redis · Chroma 컨테이너용)

### 2. 클론 후 한 번에
```bash
git clone <repo-url> mentors-backend
cd mentors-backend

uv sync                                     # 의존성
copy .env.example .env                       # Windows  (또는 cp)
docker compose up -d                         # 인프라 컨테이너
uv run alembic upgrade head                  # DB 마이그레이션
uv run uvicorn main:app --reload             # 앱 실행
```

### 3. 확인
- http://localhost:8000/health → `{"status":"ok"}`
- http://localhost:8000/docs (OpenAPI Swagger UI)

### 4. .env 채우기 (선택)
키가 없어도 앱은 부팅됨 — 해당 기능만 비활성화. 사용하려면 다음 채우기:
- `JWT_SECRET` — 32+ 바이트 랜덤 (필수)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — OAuth 사용 시
- `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY` — LLM 사용 시
- `FCM_CREDENTIALS_PATH` — 푸시 알림 사용 시

---

## 디렉토리

```
mentors-backend/             ← repo root
├── core/                    16개 코어 모듈 (코어 owner 단독)
├── features/                6개 동 (각 owner 1명)
├── migrations/              Alembic — YYYYMMDD_<owner>_*.py
├── tests/                   pytest
├── docker/                  Dockerfile 등 (필요 시)
├── docs/                    설계 자료 (참고용)
├── AGENTS.md                AI 에이전트 + 동 owner 운영 룰
├── README.md                여기
├── pyproject.toml           uv 의존성
├── docker-compose.yml       Postgres · Redis · Chroma
├── alembic.ini              마이그레이션 설정
├── main.py                  FastAPI 진입점
└── .env.example
```

---

## 도구

```bash
ruff format && ruff check        # 포맷 + 린트
mypy .                           # --strict 타입체크
pytest                           # 테스트
```

세 명령 모두 통과해야 PR 머지 가능.

---

## 다음 작업

- 동 owner: [AGENTS.md](AGENTS.md) §3 Import 룰 + §5 cookbook + 시범 PR (`features/daily_report/`) 정독 후 자기 동 작업 시작.
- 코어 변경 필요: 코어 owner에게 PR (특히 `core/contracts/` 변경 시 모든 owner 알림).
