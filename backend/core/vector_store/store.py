"""Chroma 래퍼 (§4.8). 클라이언트는 lazy 초기화 — Chroma 다운 시 앱은 부팅."""

import logging
from typing import Any

from core.config import settings
from core.exceptions import ExternalServiceError
from core.llm import llm

from .dto import Document

logger = logging.getLogger("vector_store")


class VectorStore:
    def __init__(self) -> None:
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import chromadb

                self._client = chromadb.HttpClient(
                    host=settings.chroma_host,
                    port=settings.chroma_port,
                )
            except Exception as e:
                raise ExternalServiceError(f"Chroma connect failed: {e}") from e
        return self._client

    def _collection(self, name: str) -> Any:
        return self._get_client().get_or_create_collection(name)

    async def search(
        self,
        collection: str,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[Document]:
        embedding = await llm.embed(query)
        col = self._collection(collection)
        result = col.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=filters,
        )

        docs: list[Document] = []
        documents = result.get("documents") or [[]]
        ids = result.get("ids") or [[]]
        metadatas = result.get("metadatas") or [[]]

        if not documents or not documents[0]:
            return docs

        for i, text in enumerate(documents[0]):
            doc_id = ids[0][i] if ids and len(ids[0]) > i else f"doc_{i}"
            metadata = metadatas[0][i] if metadatas and len(metadatas[0]) > i else {}
            docs.append(Document(id=str(doc_id), text=str(text), metadata=metadata or {}))
        return docs

    async def upsert(self, collection: str, docs: list[Document]) -> None:
        if not docs:
            return
        embeddings = [await llm.embed(doc.text) for doc in docs]
        col = self._collection(collection)
        col.upsert(
            ids=[d.id for d in docs],
            embeddings=embeddings,
            documents=[d.text for d in docs],
            metadatas=[d.metadata for d in docs],
        )

    async def delete(self, collection: str, ids: list[str]) -> None:
        col = self._collection(collection)
        col.delete(ids=ids)


vector_store = VectorStore()
