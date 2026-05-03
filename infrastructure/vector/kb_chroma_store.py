"""知识库专用的 ChromaDB 向量存储（每 KB 独立 collection）。"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings
from domain.knowledge_base.entity import Chunk
from domain.knowledge_base.repository import IKBVectorStore
from domain.knowledge_base.value_object import SearchResult
from infrastructure.rag.embedding import BGEChineseEmbedding

logger = logging.getLogger("sivan.kb.chroma")

_COLLECTION_PREFIX = "kb_"


def _sanitize_coll_name(kb_name: str) -> str:
    """将 KB 名称转为 ChromaDB 合法 collection 名。

    ChromaDB 约束：[a-zA-Z0-9._-]，3-512 字符。
    非 ASCII 字符用短 hash 替换。
    """
    # 全是 ASCII 字母数字 + ._- 则直接可用
    if re.fullmatch(r"[a-zA-Z0-9._-]+", kb_name):
        return kb_name
    # 含非 ASCII 字符 → 取前 48 个 ASCII-safe 字符 + hash 后缀
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", kb_name)[:48]
    suffix = hashlib.md5(kb_name.encode()).hexdigest()[:8]
    return f"{safe}_{suffix}"


class KnowledgeBaseChromaStore(IKBVectorStore):
    """知识库 ChromaDB 存储。

    每个知识库一个独立 collection（命名 kb_{kb_name}），与记忆系统互不干扰。
    使用 BGEChineseEmbedding（带降级）。
    """

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        embedding_function: chromadb.EmbeddingFunction | None = None,
    ) -> None:
        self.persist_dir = Path(persist_dir or settings.CHROMA_PATH)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self._ef = embedding_function or BGEChineseEmbedding()
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

    def _coll_name(self, kb_name: str, sanitized: bool = True) -> str:
        safe = _sanitize_coll_name(kb_name) if sanitized else kb_name
        return f"{_COLLECTION_PREFIX}{safe}"

    def _get_collection(self, kb_name: str):
        name = self._coll_name(kb_name)
        # 1) 标准名
        try:
            coll = self.client.get_collection(name=name, embedding_function=self._ef)
            return coll
        except Exception:
            pass
        # 2) 兼容旧名：升级前 collection 直接用了 kb_{kb_name} 含中文
        old_name = self._coll_name(kb_name, sanitized=False)
        if old_name != name:
            try:
                return self.client.get_collection(name=old_name, embedding_function=self._ef)
            except Exception:
                pass
        # 3) 遍历所有 collection，按 metadata.kb_name 匹配
        try:
            for c in self.client.list_collections():
                if c.name.startswith(_COLLECTION_PREFIX) and c.metadata and c.metadata.get("kb_name") == kb_name:
                    return c
        except Exception:
            pass
        # 4) 不存在 → 新建
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "kb_name": kb_name},
            embedding_function=self._ef,
        )

    def store_chunks(self, kb_name: str, chunks: list[Chunk]) -> None:
        coll = self._get_collection(kb_name)
        coll.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "doc_id": c.doc_id,
                    "chunk_index": c.chunk_index,
                    "heading": c.heading,
                    "source": c.source,
                    "kb_name": c.kb_name,
                }
                for c in chunks
            ],
        )

    def search(self, kb_name: str, query: str, top_k: int = 5) -> list[SearchResult]:
        coll = self._get_collection(kb_name)
        result = coll.query(query_texts=[query], n_results=top_k)
        return self._format_results(result, kb_name)

    def search_all(self, query: str, top_k: int = 3) -> list[SearchResult]:
        all_results: list[SearchResult] = []
        for coll_name in self.list_kb_collections():
            kb_name = coll_name[len(_COLLECTION_PREFIX) :]
            try:
                coll = self.client.get_collection(
                    name=coll_name,
                    embedding_function=self._ef,
                )
                result = coll.query(query_texts=[query], n_results=top_k)
                all_results.extend(self._format_results(result, kb_name))
            except Exception as exc:
                logger.warning("search_all 跳过 collection %s: %s", coll_name, exc)

        # 按 cosine distance 升序（越小越相似）
        all_results.sort(key=lambda r: r.score)
        return all_results[:top_k]

    def cleanup_orphaned_dirs(self) -> int:
        """清理 chroma 目录中不再被 chroma.sqlite3 引用的 UUID 文件夹。

        ChromaDB 的 delete_collection 只移除 SQLite 元数据，
        不会删除磁盘上的 segment UUID 文件夹。此方法清理这些残留。
        """
        chroma_db = self.persist_dir / "chroma.sqlite3"
        if not chroma_db.exists():
            return 0

        conn = sqlite3.connect(str(chroma_db))
        active: set[str] = set()
        for row in conn.execute("SELECT id FROM segments").fetchall():
            active.add(str(row[0]))
        conn.close()

        count = 0
        for d in self.persist_dir.iterdir():
            if d.is_dir() and len(d.name) == 36 and d.name.count("-") == 4 and d.name not in active:
                shutil.rmtree(d, ignore_errors=True)
                logger.info("清理 orphaned UUID 目录: %s", d.name)
                count += 1
        return count

    def rename_collection(self, old_name: str, new_name: str) -> None:
        """重命名 collection：创建新 collection 复制数据后删除旧 collection。"""
        old_coll_name = self._coll_name(old_name)
        new_coll_name = self._coll_name(new_name)
        if old_coll_name == new_coll_name:
            return
        try:
            old_coll = self.client.get_collection(name=old_coll_name, embedding_function=self._ef)
        except Exception:
            return  # 旧 collection 不存在则跳过

        count = old_coll.count()
        if count > 0:
            all_data = old_coll.get(include=["documents", "metadatas"])
            new_coll = self.client.get_or_create_collection(
                name=new_coll_name,
                metadata={"hnsw:space": "cosine", "kb_name": new_name},
                embedding_function=self._ef,
            )
            new_coll.add(
                ids=all_data.get("ids", []),
                documents=all_data.get("documents", []) or [],
                metadatas=all_data.get("metadatas", []) or [],
            )

        try:
            self.client.delete_collection(old_coll_name)
        except Exception:
            pass
        self.cleanup_orphaned_dirs()

    def delete_collection(self, kb_name: str) -> None:
        names = [self._coll_name(kb_name)]
        old_name = self._coll_name(kb_name, sanitized=False)
        if old_name != names[0]:
            names.append(old_name)
        for n in names:
            try:
                self.client.delete_collection(n)
            except Exception:
                pass
        self.cleanup_orphaned_dirs()

    def delete_document_chunks(self, kb_name: str, doc_id: str) -> None:
        coll = self._get_collection(kb_name)
        # 获取该文档的所有 chunk ID
        result = coll.get(where={"doc_id": doc_id})
        ids = result.get("ids", [])
        if ids:
            coll.delete(ids=ids)

    def get_document_chunks(self, kb_name: str, doc_id: str) -> list[dict]:
        """获取文档的所有分块内容。"""
        coll = self._get_collection(kb_name)
        result = coll.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
        chunks = []
        for i in range(len(result.get("ids", []))):
            chunks.append({
                "chunk_id": result["ids"][i],
                "text": result["documents"][i] if result.get("documents") else "",
                "metadata": result["metadatas"][i] if result.get("metadatas") else {},
            })
        return chunks

    def count(self, kb_name: str) -> int:
        return self._get_collection(kb_name).count()

    def list_kb_collections(self) -> list[str]:
        return [c.name for c in self.client.list_collections() if c.name.startswith(_COLLECTION_PREFIX)]

    def rebuild_index(self, kb_name: str) -> int:
        """重建单个 KB 的向量索引（重新 embedding 所有 chunk）。

        用于模型升级后重建索引。返回重建的 chunk 数。
        """
        old_coll = self._get_collection(kb_name)
        count = old_coll.count()
        if count == 0:
            return 0

        # 读出所有数据
        all_data = old_coll.get(include=["documents", "metadatas"])
        ids: list[str] = all_data.get("ids", [])
        docs: list[str] = all_data.get("documents", []) or []
        metas: list[dict] = all_data.get("metadatas", []) or []

        # 删除旧 collection
        coll_name = self._coll_name(kb_name)
        try:
            self.client.delete_collection(coll_name)
        except Exception:
            pass

        # 重建（新的 embedding_function 会在 add 时自动使用）
        new_coll = self._get_collection(kb_name)
        new_coll.add(ids=ids, documents=docs, metadatas=metas)
        self.cleanup_orphaned_dirs()
        return len(ids)

    @staticmethod
    def _format_results(
        result: dict[str, Any],
        kb_name: str = "",
    ) -> list[SearchResult]:
        items: list[SearchResult] = []
        ids_list = result.get("ids", [[]])[0]
        docs_list = result.get("documents", [[]])[0]
        metas_list = result.get("metadatas", [[]])[0]
        dists_list = result.get("distances", [[]])[0]

        for i, chunk_id in enumerate(ids_list):
            items.append(
                SearchResult(
                    chunk_id=chunk_id,
                    kb_name=kb_name or (metas_list[i] or {}).get("kb_name", ""),
                    text=docs_list[i] if docs_list and i < len(docs_list) else "",
                    score=dists_list[i] if dists_list and i < len(dists_list) else 0.0,
                    metadata=metas_list[i] if metas_list and i < len(metas_list) else {},
                )
            )
        return items
