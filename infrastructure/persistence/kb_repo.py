"""知识库元数据的 SQLite 存储。"""

from __future__ import annotations

import logging

from domain.knowledge_base.entity import Document, KnowledgeBase
from domain.knowledge_base.repository import IKBVectorStore, IKnowledgeBaseRepository
from infrastructure.persistence.connection import SQLiteConnectionManager

logger = logging.getLogger("sivan.kb.repo")


class KnowledgeBaseRepository(IKnowledgeBaseRepository):
    """SQLite 存储知识库和文档元数据。"""

    def __init__(
        self,
        connection_manager: SQLiteConnectionManager,
        vector_store: IKBVectorStore,
    ) -> None:
        self._db = connection_manager
        self._vector = vector_store
        self._init_tables()

    def _init_tables(self) -> None:
        """初始化表（FTS5 虚拟表由 Alembic 不支持，在此手动创建）。"""
        conn = self._db.connection
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS kb_documents_fts USING fts5(
                    doc_id UNINDEXED, kb_name UNINDEXED, filename UNINDEXED, text_content,
                    tokenize='unicode61'
                )
            """)
        except Exception as exc:
            logger.warning("FTS5 虚拟表创建失败（不影响基础功能）: %s", exc)
        conn.commit()

    def create_kb(self, kb: KnowledgeBase) -> str:
        conn = self._db.connection
        conn.execute(
            "INSERT OR REPLACE INTO knowledge_bases (kb_name, description) VALUES (?, ?)",
            (kb.kb_name, kb.description),
        )
        conn.commit()
        return kb.kb_name

    def delete_kb(self, kb_name: str) -> bool:
        self._vector.delete_collection(kb_name)
        conn = self._db.connection
        docs = conn.execute("SELECT doc_id FROM kb_documents WHERE kb_name=?", (kb_name,)).fetchall()
        conn.execute("DELETE FROM kb_documents WHERE kb_name=?", (kb_name,))
        conn.execute("DELETE FROM knowledge_bases WHERE kb_name=?", (kb_name,))
        conn.commit()
        # 清理 FTS 索引
        for row in docs:
            self._delete_fts_row(row[0])
        return True

    def get_kb(self, kb_name: str) -> KnowledgeBase | None:
        conn = self._db.connection
        conn.row_factory = __import__("sqlite3").Row
        row = conn.execute("SELECT * FROM knowledge_bases WHERE kb_name=?", (kb_name,)).fetchone()
        conn.row_factory = None
        if not row:
            return None
        return KnowledgeBase(**dict(row))

    def list_kbs(self) -> list[KnowledgeBase]:
        conn = self._db.connection
        conn.row_factory = __import__("sqlite3").Row
        rows = conn.execute("SELECT * FROM knowledge_bases ORDER BY created_at DESC").fetchall()
        conn.row_factory = None
        return [KnowledgeBase(**dict(r)) for r in rows]

    def count_kbs(self) -> int:
        conn = self._db.connection
        return conn.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()[0]

    def list_kbs_paginated(self, page: int = 1, page_size: int = 20) -> tuple[list[KnowledgeBase], int]:
        """分页查询 KB，返回 (items, total)。"""
        conn = self._db.connection
        conn.row_factory = __import__("sqlite3").Row
        total = conn.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM knowledge_bases ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
        conn.row_factory = None
        return [KnowledgeBase(**dict(r)) for r in rows], total

    def delete_kbs(self, kb_names: list[str]) -> int:
        """批量删除 KB。返回删除数。"""
        if not kb_names:
            return 0
        for name in kb_names:
            self._vector.delete_collection(name)
        conn = self._db.connection
        placeholders = ",".join("?" for _ in kb_names)
        doc_rows = conn.execute(f"SELECT doc_id FROM kb_documents WHERE kb_name IN ({placeholders})", kb_names).fetchall()
        conn.execute(f"DELETE FROM kb_documents WHERE kb_name IN ({placeholders})", kb_names)
        conn.execute(f"DELETE FROM knowledge_bases WHERE kb_name IN ({placeholders})", kb_names)
        conn.commit()
        for row in doc_rows:
            self._delete_fts_row(row[0])
        return len(kb_names)

    def _delete_fts_row(self, doc_id: str) -> None:
        try:
            conn = self._db.connection
            rows = conn.execute("SELECT rowid FROM kb_documents_fts WHERE doc_id=?", (doc_id,)).fetchall()
            for r in rows:
                conn.execute("DELETE FROM kb_documents_fts WHERE rowid=?", (r[0],))
        except Exception:
            pass

    def save_document(self, doc: Document) -> str:
        conn = self._db.connection
        conn.execute(
            "INSERT OR REPLACE INTO kb_documents "
            "(doc_id, kb_name, filename, source_path, file_type, chunk_count, char_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc.doc_id, doc.kb_name, doc.filename, doc.source_path, doc.file_type, doc.chunk_count, doc.char_count),
        )
        conn.commit()
        return doc.doc_id

    def delete_document(self, doc_id: str) -> bool:
        conn = self._db.connection
        conn.execute("DELETE FROM kb_documents WHERE doc_id=?", (doc_id,))
        conn.commit()
        self._delete_fts_row(doc_id)
        return True

    def get_documents(self, kb_name: str) -> list[Document]:
        conn = self._db.connection
        conn.row_factory = __import__("sqlite3").Row
        rows = conn.execute(
            "SELECT * FROM kb_documents WHERE kb_name=? ORDER BY created_at DESC",
            (kb_name,),
        ).fetchall()
        conn.row_factory = None
        return [Document(**dict(r)) for r in rows]

    def count_documents(self, kb_name: str) -> int:
        conn = self._db.connection
        return conn.execute("SELECT COUNT(*) FROM kb_documents WHERE kb_name=?", (kb_name,)).fetchone()[0]

    def get_documents_paginated(self, kb_name: str, page: int = 1, page_size: int = 20) -> tuple[list[Document], int]:
        """分页查询文档，返回 (items, total)。"""
        conn = self._db.connection
        conn.row_factory = __import__("sqlite3").Row
        total = conn.execute("SELECT COUNT(*) FROM kb_documents WHERE kb_name=?", (kb_name,)).fetchone()[0]
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT * FROM kb_documents WHERE kb_name=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (kb_name, page_size, offset),
        ).fetchall()
        conn.row_factory = None
        return [Document(**dict(r)) for r in rows], total

    def get_document(self, doc_id: str) -> Document | None:
        """获取单个文档详情（含 text_content）。"""
        conn = self._db.connection
        conn.row_factory = __import__("sqlite3").Row
        row = conn.execute(
            "SELECT * FROM kb_documents WHERE doc_id=?", (doc_id,),
        ).fetchone()
        conn.row_factory = None
        return Document(**dict(row)) if row else None

    def delete_documents_batch(self, doc_ids: list[str]) -> int:
        """批量删除文档。返回删除数。"""
        if not doc_ids:
            return 0
        conn = self._db.connection
        placeholders = ",".join("?" for _ in doc_ids)
        conn.execute(f"DELETE FROM kb_documents WHERE doc_id IN ({placeholders})", doc_ids)
        conn.commit()
        return len(doc_ids)

    def rename_kb(self, old_name: str, new_name: str) -> bool:
        """重命名知识库（级联更新文档表 + 向量集合）。"""
        if old_name == new_name:
            return True
        # 检查新名称是否已存在
        exists = self._db.connection.execute(
            "SELECT 1 FROM knowledge_bases WHERE kb_name=?", (new_name,)
        ).fetchone()
        if exists:
            raise ValueError(f"知识库 '{new_name}' 已存在")
        # 重命名向量集合
        self._vector.rename_collection(old_name, new_name)
        conn = self._db.connection
        # 先更新父表（解除 FK 约束），再更新子表
        conn.execute(
            "UPDATE knowledge_bases SET kb_name=?, updated_at=CURRENT_TIMESTAMP WHERE kb_name=?",
            (new_name, old_name),
        )
        conn.execute("UPDATE kb_documents SET kb_name=? WHERE kb_name=?", (new_name, old_name))
        conn.commit()
        return True

    def update_document_filename(self, doc_id: str, new_filename: str) -> bool:
        """更新文档文件名。"""
        conn = self._db.connection
        conn.execute("UPDATE kb_documents SET filename=? WHERE doc_id=?", (new_filename, doc_id))
        conn.commit()
        return True

    def save_document_text(self, doc_id: str, kb_name: str, filename: str, text: str) -> None:
        """持久化文档全文并更新 FTS 索引。"""
        conn = self._db.connection
        conn.execute(
            "UPDATE kb_documents SET text_content=? WHERE doc_id=?",
            (text, doc_id),
        )
        # 更新 FTS 索引（删除旧记录后插入）
        self._delete_fts_row(doc_id)
        try:
            conn.execute(
                "INSERT INTO kb_documents_fts (doc_id, kb_name, filename, text_content) VALUES (?, ?, ?, ?)",
                (doc_id, kb_name, filename, text),
            )
        except Exception:
            pass
        conn.commit()

    def delete_document_fts(self, doc_id: str) -> None:
        """从 FTS 索引中删除文档。"""
        self._delete_fts_row(doc_id)

    def search_fts(self, query: str, kb_name: str | None = None, limit: int = 20) -> list[dict]:
        """FTS5 全文检索，返回 [{doc_id, kb_name, filename, snippet, rank}]。"""
        results: list[dict] = []
        try:
            conn = self._db.connection
            if kb_name:
                sql = (
                    "SELECT rowid, doc_id, kb_name, filename, rank "
                    "FROM kb_documents_fts WHERE kb_documents_fts MATCH ? AND kb_name=? "
                    "ORDER BY rank LIMIT ?"
                )
                rows = conn.execute(sql, (query, kb_name, limit)).fetchall()
            else:
                sql = (
                    "SELECT rowid, doc_id, kb_name, filename, rank "
                    "FROM kb_documents_fts WHERE kb_documents_fts MATCH ? "
                    "ORDER BY rank LIMIT ?"
                )
                rows = conn.execute(sql, (query, limit)).fetchall()
            for row in rows:
                results.append({
                    "doc_id": row[1],
                    "kb_name": row[2],
                    "filename": row[3],
                    "rank": row[4],
                    "snippet": self._fts_snippet(row[0], query),
                })
        except Exception as exc:
            logger.warning("FTS 检索失败: %s", exc)
        return results

    def _fts_snippet(self, fts_rowid: int, query: str) -> str:
        """从 FTS 结果提取带关键词上下文的片段。"""
        try:
            conn = self._db.connection
            row = conn.execute(
                "SELECT snippet(kb_documents_fts, 3, '<mark>', '</mark>', '...', 32) FROM kb_documents_fts WHERE rowid=?",
                (fts_rowid,),
            ).fetchone()
            return row[0] if row else ""
        except Exception:
            return ""

    def get_global_stats(self) -> dict:
        """获取全局统计（文档总数、分块总数）。"""
        conn = self._db.connection
        row = conn.execute(
            "SELECT COALESCE(SUM(document_count),0), COALESCE(SUM(chunk_count),0) FROM knowledge_bases"
        ).fetchone()
        # 也直接从 kb_documents 统计，避免向量存储未写入时 knowledge_bases 分块数为 0
        doc_row = conn.execute(
            "SELECT COALESCE(COUNT(*),0), COALESCE(SUM(chunk_count),0) FROM kb_documents"
        ).fetchone()
        total_docs = max(row[0], doc_row[0])
        total_chunks = max(row[1], doc_row[1])
        return {"total_documents": total_docs, "total_chunks": total_chunks}

    def update_kb_description(self, kb_name: str, description: str) -> None:
        conn = self._db.connection
        conn.execute(
            "UPDATE knowledge_bases SET description=?, updated_at=CURRENT_TIMESTAMP WHERE kb_name=?",
            (description, kb_name),
        )
        conn.commit()

    def get_document_chunk_sum(self, kb_name: str) -> int:
        """SQLite 中文档记录的 chunk_count 总和（向量存储未成功时回退用）。"""
        conn = self._db.connection
        row = conn.execute(
            "SELECT COALESCE(SUM(chunk_count),0) FROM kb_documents WHERE kb_name=?", (kb_name,)
        ).fetchone()
        return row[0]

    def update_kb_stats(self, kb_name: str) -> None:
        conn = self._db.connection
        doc_count = conn.execute("SELECT COUNT(*) as cnt FROM kb_documents WHERE kb_name=?", (kb_name,)).fetchone()[0]
        vec_count = self._vector.count(kb_name)
        # 向量存储可能为 0（早期版本不支持中文集合名），回退到 SQLite 的文档分块总和
        chunk_count = vec_count if vec_count > 0 else self.get_document_chunk_sum(kb_name)
        conn.execute(
            "UPDATE knowledge_bases SET document_count=?, chunk_count=?, updated_at=CURRENT_TIMESTAMP WHERE kb_name=?",
            (doc_count, chunk_count, kb_name),
        )
        conn.commit()
