from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Chroma의 cosine distance (0=동일, 1=직교, 2=정반대).
    # search 결과에서만 채워지고 upsert 시엔 무시됨.
    distance: float | None = None


__all__ = ["Document"]
