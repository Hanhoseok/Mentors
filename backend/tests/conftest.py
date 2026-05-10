"""Pytest 공용 설정.

env 변수 셋업은 .env에 의존. CI에서는 export 또는 pytest-env 사용 권장.
"""

import os

os.environ.setdefault("ENV", "dev")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://mentors:mentors@localhost:5432/mentors",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-only-32bytes-secret-please-replace-me")
os.environ.setdefault("GOOGLE_CLIENT_ID", "dev")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "dev")
