"""知识库应用服务。"""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from domain.knowledge_base.entity import Document, KnowledgeBase
from domain.knowledge_base.repository import IKBVectorStore, IKnowledgeBaseRepository
from infrastructure.rag.document_processor import DocumentParser, RecursiveChunkSplitter

logger = logging.getLogger("sivan.kb.service")

# RAG 默认值（通过 DB settings 表覆盖，见 interfaces/api/services/settings.py）
_RAG_CHUNK_SIZE = 500
_RAG_CHUNK_OVERLAP = 50
_RAG_DEFAULT_TOP_K = 5


class KnowledgeBaseService:
    """知识库服务：组合解析、分块、向量存储、检索。"""

    def __init__(
        self,
        kb_repo: IKnowledgeBaseRepository,
        vector_store: IKBVectorStore,
        chunk_size: int = _RAG_CHUNK_SIZE,
        chunk_overlap: int = _RAG_CHUNK_OVERLAP,
    ) -> None:
        self._repo = kb_repo
        self._vector = vector_store
        self._parser = DocumentParser()
        self._splitter = RecursiveChunkSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def create_knowledge_base(self, name: str, description: str = "") -> dict:
        """创建知识库。"""
        kb = KnowledgeBase(kb_name=name, description=description)
        self._repo.create_kb(kb)
        return {"kb_name": name, "description": description, "success": True}

    def delete_knowledge_base(self, name: str) -> bool:
        """删除知识库（含向量）。"""
        return self._repo.delete_kb(name)

    def list_knowledge_bases(self) -> list[dict]:
        """列出所有知识库及统计。"""
        kbs = self._repo.list_kbs()
        result = []
        for kb in kbs:
            try:
                vec_count = self._vector.count(kb.kb_name)
            except Exception:
                vec_count = 0
            chunk_count = vec_count if vec_count > 0 else self._repo.get_document_chunk_sum(kb.kb_name)
            result.append(
                {
                    "kb_name": kb.kb_name,
                    "description": kb.description,
                    "document_count": kb.document_count,
                    "chunk_count": chunk_count,
                    "created_at": kb.created_at.isoformat()
                    if hasattr(kb.created_at, "isoformat")
                    else str(kb.created_at),
                    "updated_at": kb.updated_at.isoformat()
                    if hasattr(kb.updated_at, "isoformat")
                    else str(kb.updated_at),
                }
            )
        return result

    def list_knowledge_bases_paginated(self, page: int = 1, page_size: int = 20) -> dict:
        """分页列出知识库。返回 {items, total, page, page_size}。"""
        kbs, total = self._repo.list_kbs_paginated(page, page_size)
        items = []
        for kb in kbs:
            try:
                vec_count = self._vector.count(kb.kb_name)
            except Exception:
                vec_count = 0
            chunk_count = vec_count if vec_count > 0 else self._repo.get_document_chunk_sum(kb.kb_name)
            items.append(
                {
                    "kb_name": kb.kb_name,
                    "description": kb.description,
                    "document_count": kb.document_count,
                    "chunk_count": chunk_count,
                    "created_at": kb.created_at.isoformat()
                    if hasattr(kb.created_at, "isoformat")
                    else str(kb.created_at),
                    "updated_at": kb.updated_at.isoformat()
                    if hasattr(kb.updated_at, "isoformat")
                    else str(kb.updated_at),
                }
            )
        stats = self._repo.get_global_stats()
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_documents": stats["total_documents"],
            "total_chunks": stats["total_chunks"],
        }

    def get_knowledge_base(self, name: str) -> dict | None:
        """获取知识库详情。"""
        kb = self._repo.get_kb(name)
        if not kb:
            return None
        try:
            vec_count = self._vector.count(kb.kb_name)
        except Exception:
            vec_count = 0
        chunk_count = vec_count if vec_count > 0 else self._repo.get_document_chunk_sum(kb.kb_name)
        docs = self._repo.get_documents(kb.kb_name)
        return {
            "kb_name": kb.kb_name,
            "description": kb.description,
            "document_count": kb.document_count,
            "chunk_count": chunk_count,
            "created_at": str(kb.created_at),
            "updated_at": str(kb.updated_at),
            "documents": [
                {
                    "doc_id": d.doc_id,
                    "filename": d.filename,
                    "file_type": d.file_type,
                    "chunk_count": d.chunk_count,
                    "char_count": d.char_count,
                    "created_at": str(d.created_at),
                }
                for d in docs
            ],
        }

    def get_knowledge_base_paginated(self, name: str, page: int = 1, page_size: int = 20) -> dict | None:
        """获取知识库详情（文档分页）。返回 {kb_info, documents: {items, total, page, page_size}}。"""
        kb = self._repo.get_kb(name)
        if not kb:
            return None
        try:
            vec_count = self._vector.count(kb.kb_name)
        except Exception:
            vec_count = 0
        chunk_count = vec_count if vec_count > 0 else self._repo.get_document_chunk_sum(kb.kb_name)
        docs, doc_total = self._repo.get_documents_paginated(kb.kb_name, page, page_size)
        return {
            "kb_name": kb.kb_name,
            "description": kb.description,
            "document_count": kb.document_count,
            "chunk_count": chunk_count,
            "created_at": str(kb.created_at),
            "updated_at": str(kb.updated_at),
            "documents": {
                "items": [
                    {
                        "doc_id": d.doc_id,
                        "filename": d.filename,
                        "file_type": d.file_type,
                        "chunk_count": d.chunk_count,
                        "char_count": d.char_count,
                        "created_at": str(d.created_at),
                    }
                    for d in docs
                ],
                "total": doc_total,
                "page": page,
                "page_size": page_size,
            },
        }

    def rename_knowledge_base(self, old_name: str, new_name: str, description: str | None = None) -> dict:
        """重命名知识库（可选更新描述）。"""
        if old_name != new_name:
            try:
                self._repo.rename_kb(old_name, new_name)
            except ValueError as e:
                return {"success": False, "error": str(e)}
        # 更新描述
        if description is not None:
            self._repo.update_kb_description(new_name, description)
        return {"success": True, "kb_name": new_name}

    def get_document_detail(self, kb_name: str, doc_id: str) -> dict | None:
        """获取文档详情（含全文内容和分块列表）。"""
        doc = self._repo.get_document(doc_id)
        if not doc:
            return None
        # 获取分块
        try:
            chunks = self._vector.get_document_chunks(kb_name, doc_id)
        except Exception:
            chunks = []
        return {
            "doc_id": doc.doc_id,
            "kb_name": doc.kb_name,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "char_count": doc.char_count,
            "chunk_count": doc.chunk_count,
            "text_content": doc.text_content,
            "created_at": str(doc.created_at),
            "chunks": chunks,
        }

    def rename_document(self, doc_id: str, new_filename: str) -> dict:
        """更新文档文件名。"""
        self._repo.update_document_filename(doc_id, new_filename)
        return {"success": True, "doc_id": doc_id, "filename": new_filename}

    def delete_knowledge_bases_batch(self, names: list[str]) -> int:
        """批量删除知识库。返回成功删除数。"""
        return self._repo.delete_kbs(names)

    def delete_document_batch(self, doc_ids: list[str]) -> int:
        """批量删除文档。返回成功删除数。"""
        return self._repo.delete_documents_batch(doc_ids)

    def ingest_file(self, kb_name: str, file_path: str) -> dict:
        """导入文件到知识库。"""
        # 确保 KB 存在
        kb = self._repo.get_kb(kb_name)
        if not kb:
            self._repo.create_kb(KnowledgeBase(kb_name=kb_name))

        path = Path(file_path)
        text, meta = self._parser.read(str(path))

        # 文档记录
        doc_id = uuid.uuid4().hex
        doc = Document(
            doc_id=doc_id,
            kb_name=kb_name,
            filename=meta["filename"],
            source_path=str(path.resolve()),
            file_type=meta["file_type"],
            char_count=meta["char_count"],
        )

        # 分块
        chunks = self._splitter.split(
            text,
            kb_name=kb_name,
            doc_id=doc_id,
            source=meta["filename"],
            headings=meta.get("headings"),
        )

        doc.chunk_count = len(chunks)
        self._repo.save_document(doc)
        self._repo.save_document_text(doc_id, kb_name, meta["filename"], text)
        self._vector.store_chunks(kb_name, chunks)
        self._repo.update_kb_stats(kb_name)

        return {
            "doc_id": doc_id,
            "filename": meta["filename"],
            "char_count": meta["char_count"],
            "chunk_count": len(chunks),
            "kb_name": kb_name,
            "success": True,
        }

    def ingest_text(self, kb_name: str, text: str, filename: str = "inline.txt") -> dict:
        """直接导入文本（无需文件）。"""
        kb = self._repo.get_kb(kb_name)
        if not kb:
            self._repo.create_kb(KnowledgeBase(kb_name=kb_name))

        doc_id = uuid.uuid4().hex
        doc = Document(
            doc_id=doc_id,
            kb_name=kb_name,
            filename=filename,
            source_path="inline",
            file_type=Path(filename).suffix[1:] or "txt",
            char_count=len(text),
        )

        chunks = self._splitter.split(
            text,
            kb_name=kb_name,
            doc_id=doc_id,
            source=filename,
        )

        doc.chunk_count = len(chunks)
        self._repo.save_document(doc)
        self._repo.save_document_text(doc_id, kb_name, filename, text)
        self._vector.store_chunks(kb_name, chunks)
        self._repo.update_kb_stats(kb_name)

        return {
            "doc_id": doc_id,
            "filename": filename,
            "char_count": len(text),
            "chunk_count": len(chunks),
            "kb_name": kb_name,
            "success": True,
        }

    def ingest_bytes(self, kb_name: str, filename: str, content: bytes) -> dict:
        """导入原始字节内容（用于 Web 上传）。"""
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return self.ingest_file(kb_name, tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def search(self, kb_name: str, query: str, top_k: int | None = None, mode: str = "vector") -> list[dict]:
        """搜索单个知识库。mode: vector / fts。"""
        k = top_k or _RAG_DEFAULT_TOP_K
        if mode == "fts":
            return self._repo.search_fts(query, kb_name=kb_name, limit=k)
        results = self._vector.search(kb_name, query, top_k=k)
        return [
            {
                "chunk_id": r.chunk_id,
                "kb_name": r.kb_name,
                "text": r.text,
                "score": 1.0 - r.score,
                "metadata": r.metadata,
            }
            for r in results
        ]

    def rebuild_all_indexes(self) -> dict[str, int]:
        """重建所有知识库的向量索引（重新 embedding）。

        用于模型升级后调用。返回 {kb_name: rebuilt_chunk_count}。
        """
        kbs = self._repo.list_kbs()
        result: dict[str, int] = {}
        for kb in kbs:
            try:
                cnt = self._vector.rebuild_index(kb.kb_name)
                if cnt == 0:
                    # 向量存储为空（如早期版本不支持中文集合名），回退到 SQLite 文档记录
                    cnt = self._repo.get_document_chunk_sum(kb.kb_name)
                result[kb.kb_name] = cnt
                self._repo.update_kb_stats(kb.kb_name)
                logger.info("重建索引 %s: %d chunks", kb.kb_name, cnt)
            except Exception as exc:
                logger.error("重建索引失败 %s: %s", kb.kb_name, exc)
                result[kb.kb_name] = 0
        return result

    def search_by_kb_names(self, kb_names: list[str], query: str, top_k: int | None = None) -> list[dict]:
        """在指定知识库列表中搜索（项目隔离用）。"""
        k = top_k or _RAG_DEFAULT_TOP_K
        top_k_per_kb = max(1, k // len(kb_names)) if kb_names else k
        results: list[dict] = []
        for name in kb_names:
            try:
                results.extend(self.search(name, query, top_k=top_k_per_kb))
            except Exception:
                continue
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:k]

    def search_all(self, query: str, top_k: int | None = None, mode: str = "vector") -> list[dict]:
        """搜索所有知识库。mode: vector / fts。"""
        k = top_k or _RAG_DEFAULT_TOP_K
        if mode == "fts":
            return self._repo.search_fts(query, kb_name=None, limit=k)
        results = self._vector.search_all(query, top_k=k)
        return [
            {
                "chunk_id": r.chunk_id,
                "kb_name": r.kb_name,
                "text": r.text,
                "score": 1.0 - r.score,
                "metadata": r.metadata,
            }
            for r in results
        ]

    def search_fts(self, query: str, kb_name: str | None = None, limit: int = 20) -> list[dict]:
        """全文检索（简单封装）。"""
        return self._repo.search_fts(query, kb_name=kb_name, limit=limit)
