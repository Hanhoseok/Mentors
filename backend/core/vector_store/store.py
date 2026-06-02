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
        """벡터 시맨틱 검색. 결과 Document.distance에 cosine distance 채워서 반환.

        Chroma는 distance 작을수록 가까운 매칭. 호출자가 임계값으로 거를 수 있게
        그대로 노출 — 0.0(동일) ~ 2.0(정반대).
        """
        embedding = await llm.embed(query)
        col = self._collection(collection)
        result = col.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=filters,
            include=["documents", "metadatas", "distances"],
        )

        docs: list[Document] = []
        documents = result.get("documents") or [[]]
        ids = result.get("ids") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        if not documents or not documents[0]:
            return docs

        for i, text in enumerate(documents[0]):
            doc_id = ids[0][i] if ids and len(ids[0]) > i else f"doc_{i}"
            metadata = metadatas[0][i] if metadatas and len(metadatas[0]) > i else {}
            distance = (
                float(distances[0][i])
                if distances and len(distances[0]) > i and distances[0][i] is not None
                else None
            )
            docs.append(
                Document(
                    id=str(doc_id),
                    text=str(text),
                    metadata=metadata or {},
                    distance=distance,
                )
            )
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
