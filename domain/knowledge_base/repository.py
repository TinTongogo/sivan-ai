"""知识库仓储接口（依赖倒置）。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.knowledge_base.entity import Chunk, Document, KnowledgeBase
from domain.knowledge_base.value_object import SearchResult


class IKnowledgeBaseRepository(ABC):
    """知识库元数据的 SQLite 存储接口。"""

    @abstractmethod
    def create_kb(self, kb: KnowledgeBase) -> str: ...

    @abstractmethod
    def delete_kb(self, kb_name: str) -> bool: ...

    @abstractmethod
    def get_kb(self, kb_name: str) -> KnowledgeBase | None: ...

    @abstractmethod
    def list_kbs(self) -> list[KnowledgeBase]: ...

    @abstractmethod
    def save_document(self, doc: Document) -> str: ...

    @abstractmethod
    def delete_document(self, doc_id: str) -> bool: ...

    @abstractmethod
    def get_documents(self, kb_name: str) -> list[Document]: ...

    @abstractmethod
    def get_document(self, doc_id: str) -> Document | None: ...

    @abstractmethod
    def rename_kb(self, old_name: str, new_name: str) -> bool: ...

    @abstractmethod
    def update_document_filename(self, doc_id: str, new_filename: str) -> bool: ...

    @abstractmethod
    def update_kb_description(self, kb_name: str, description: str) -> None: ...

    @abstractmethod
    def get_document_chunk_sum(self, kb_name: str) -> int: ...

    @abstractmethod
    def save_document_text(self, doc_id: str, kb_name: str, filename: str, text: str) -> None: ...

    @abstractmethod
    def delete_document_fts(self, doc_id: str) -> None: ...

    @abstractmethod
    def search_fts(self, query: str, kb_name: str | None, limit: int = 20) -> list[dict]: ...

    @abstractmethod
    def update_kb_stats(self, kb_name: str) -> None: ...


class IKBVectorStore(ABC):
    """知识库向量存储接口（ChromaDB）。"""

    @abstractmethod
    def store_chunks(self, kb_name: str, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    def search(self, kb_name: str, query: str, top_k: int = 5) -> list[SearchResult]: ...

    @abstractmethod
    def search_all(self, query: str, top_k: int = 3) -> list[SearchResult]: ...

    @abstractmethod
    def rename_collection(self, old_name: str, new_name: str) -> None: ...

    @abstractmethod
    def delete_collection(self, kb_name: str) -> None: ...

    @abstractmethod
    def delete_document_chunks(self, kb_name: str, doc_id: str) -> None: ...

    @abstractmethod
    def get_document_chunks(self, kb_name: str, doc_id: str) -> list[dict]: ...

    @abstractmethod
    def count(self, kb_name: str) -> int: ...

    @abstractmethod
    def list_kb_collections(self) -> list[str]: ...
