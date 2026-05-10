"""콘텐츠 동 — 앱 시작 시 ContentReader 등록."""

from core.read_services import register_content_reader

from .read_service import ContentReadServiceImpl
from .router import router

register_content_reader(ContentReadServiceImpl())

__all__ = ["router"]
