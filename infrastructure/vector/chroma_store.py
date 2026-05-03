"""ChromaDB 向量存储封装。

提供记忆专用的向量存储接口，基于 ChromaDB PersistentClient。
自动处理 embedding 生成、相似度搜索、元数据过滤。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.types import EmbeddingFunction
from chromadb.config import Settings as ChromaSettings

from config.settings import settings

logger = logging.getLogger("sivan.chroma")

# 确认 HuggingFace 镜像站配置
_hf_endpoint = settings.HF_ENDPOINT
logger.debug("HuggingFace endpoint: %s", _hf_endpoint)


class ChromaStore:
    """ChromaDB 向量存储封装。

    职责：
    - 记忆文本的向量化存储 (自动 embedding)
    - 语义相似度搜索 (HNSW 加速)
    - 按 level/scope_id 元数据过滤
    - 向量持久化到 data/chroma/ 目录
    """

    _instance: ChromaStore | None = None

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        embedding_function: EmbeddingFunction | None = None,
    ) -> None:
        self.persist_dir = Path(persist_dir or settings.CHROMA_PATH)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        if embedding_function is None:
            raise ValueError(
                "ChromaStore 需要 embedding_function 参数。"
                "请传入 BGEChineseEmbedding 实例。"
            )

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        self.collection = self.client.get_or_create_collection(
            name="sivan_memories",
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_function,
        )

    @classmethod
    def get_instance(cls, persist_dir: str | Path | None = None) -> ChromaStore:
        if cls._instance is None:
            cls._instance = cls(persist_dir)
        return cls._instance

    def store(
        self,
        memory_id: str,
        text: str,
        level: str,
        scope_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """存储记忆文本及元数据。Chroma 自动生成 embedding。

        Args:
            memory_id: 唯一标识 (与 SQLite 中的 memory_id 一致)
            text: 记忆文本内容
            level: 记忆层级 (session/user/team/project)
            scope_id: 作用域 ID
            metadata: 额外元数据
        """
        self.collection.add(
            ids=[memory_id],
            documents=[text],
            metadatas=[{
                "level": level,
                "scope_id": scope_id,
                **(metadata or {}),
            }],
        )

    def search(
        self,
        query: str,
        level: str | None = None,
        scope_id: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """语义搜索记忆。

        Args:
            query: 搜索文本
            level: 过滤层级
            scope_id: 过滤作用域
            top_k: 返回条数

        Returns:
            list[dict]: [{id, document, metadata, distance}, ...]
        """
        where_filters: dict[str, Any] = {}
        if level:
            where_filters["level"] = level
        if scope_id:
            where_filters["scope_id"] = scope_id

        result = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filters or None,
        )

        items = []
        if result["ids"] and result["ids"][0]:
            for i, doc_id in enumerate(result["ids"][0]):
                items.append({
                    "id": doc_id,
                    "document": result["documents"][0][i] if result["documents"] else "",
                    "metadata": result["metadatas"][0][i] if result["metadatas"] else {},
                    "distance": result["distances"][0][i] if result["distances"] else 0.0,
                })
        return items

    def delete(self, memory_id: str) -> None:
        """删除向量。"""
        self.collection.delete(ids=[memory_id])

    def count(self) -> int:
        """当前向量总数。"""
        return self.collection.count()

    def reset(self) -> None:
        """重置集合 (用于测试)。"""
        ef = self.collection._embedding_function
        self.client.delete_collection("sivan_memories")
        self.collection = self.client.get_or_create_collection(
            name="sivan_memories",
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例。"""
        cls._instance = None
