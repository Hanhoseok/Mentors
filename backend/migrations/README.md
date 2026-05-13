# 마이그레이션 (Alembic)

> 명세서 §6.5 / ADR-009. AGENTS.md §5.9도 참조.

## 파일명 컨벤션

`migrations/versions/YYYYMMDD_<owner>_<설명>.py`

- owner 코드: `core` / `onboarding` / `learning` / `growth` / `debate` / `content` / `daily_report`
- 같은 날 같은 owner 마이그레이션이 여러 개일 경우 시간 suffix: `20260514_1430_learning_*.py`

예시:
```
20260512_core_init_users.py
20260512_core_init_device_tokens.py
20260514_learning_create_chat_messages.py
```

## 새 마이그레이션 만들기

```bash
# 1. autogenerate (자기 동의 models.py 변경 후)
uv run alembic revision --autogenerate -m "<owner>: <설명>"

# 2. 생성된 파일명을 컨벤션에 맞게 rename
#    (예: 2026_05_14_abc123_learning_create_chat.py
#         → 20260514_learning_create_chat.py)

# 3. 직접 작성한 마이그레이션이라면:
uv run alembic revision -m "<owner>: <설명>"
```

## 적용

```bash
uv run alembic upgrade head      # 최신까지
uv run alembic upgrade +1        # 한 단계
uv run alembic downgrade -1      # 되돌리기
uv run alembic current           # 현재 head
uv run alembic history           # 전체 이력
```

## 동시 PR 시 충돌

다른 owner의 마이그레이션이 먼저 머지된 경우, 자기 PR의 `down_revision`을 새 head로 다시 가리키도록 수정해야 한다. **PR 머지 직전 코어 owner와 협의**하여 순서 조정.

## env.py에 모델 등록

새 동의 SQLAlchemy 모델은 [env.py](env.py) 상단의 import 영역에 추가해야 `Base.metadata`에 등록되어 autogenerate가 인식한다.
