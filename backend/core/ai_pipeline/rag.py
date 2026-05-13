"""RAG 검색·컨텍스트 조립 (§4.13)."""

from typing import Any

from pydantic import BaseModel

from core.vector_store import Document, vector_store


class RAGContext(BaseModel):
    documents: list[Document]
    query: str

    @property
    def is_empty(self) -> bool:
        return len(self.documents) == 0

    def as_context_text(self) -> str:
        if not self.documents:
            return ""
        parts = [f"[출처: {d.id}]\n{d.text}" for d in self.documents]
        return "\n\n".join(parts)


class RAGPipeline:
    async def retrieve(
        self,
        query: str,
        collection: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> RAGContext:
        docs = await vector_store.search(collection, query, top_k=top_k, filters=filters)
        return RAGContext(documents=docs, query=query)


rag = RAGPipeline()

__all__ = ["RAGContext", "RAGPipeline", "rag"]
