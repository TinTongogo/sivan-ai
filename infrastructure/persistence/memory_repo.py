"""记忆仓库 SQLite 实现。

实现 IMemoryRepository 接口，使用 SQLite 持久化记忆条目，
集成 ChromaDB 进行向量语义检索。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime

from domain.common.value_object import MemoryLevel
from domain.memory.entity import MemoryEntry
from domain.memory.repository import IMemoryRepository
from domain.memory.value_object import MemoryQuery, MemoryStats
from infrastructure.persistence.connection import SQLiteConnectionManager
from infrastructure.vector.chroma_store import ChromaStore


class MemoryRepository(IMemoryRepository):
    """记忆仓库 SQLite 实现。

    组合 SQLite (结构化数据) + ChromaDB (向量语义检索)：
    - metadata JSON 存储在 SQLite 便于结构化查询
    - 内容向量存储在 ChromaDB 用于语义检索
    - 同一 memory_id 关联两边
    """

    def __init__(
        self,
        connection_manager: SQLiteConnectionManager,
        chroma_store: ChromaStore,
    ) -> None:
        self._db = connection_manager
        self._chroma = chroma_store
        self._init_tables()

    def _init_tables(self) -> None:
        pass  # schema 由 Alembic 管理

    def save(self, entry: MemoryEntry) -> str:
        if not entry.memory_id:
            entry.memory_id = str(uuid.uuid4())

        now = datetime.now()
        self._db.execute(
            """INSERT OR REPLACE INTO memory_entries
               (memory_id, level, scope_id, content, metadata_json,
                created_at, last_accessed_at, access_count, retention, is_archived, is_important, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.memory_id,
                entry.level.value,
                entry.scope_id,
                entry.content,
                json.dumps(entry.metadata, ensure_ascii=False),
                entry.created_at.isoformat(),
                entry.last_accessed_at.isoformat(),
                entry.access_count,
                entry.retention,
                1 if entry.is_archived else 0,
                1 if entry.is_important else 0,
                entry.summary,
            ),
        )
        self._db.commit()

        # 同步到 ChromaDB (仅 team/project 层级)
        if entry.level.use_vector:
            self._chroma.store(
                memory_id=entry.memory_id,
                text=entry.content,
                level=entry.level.value,
                scope_id=entry.scope_id,
                metadata=entry.metadata,
            )

        return entry.memory_id

    def update(self, entry: MemoryEntry) -> None:
        self._db.execute(
            """UPDATE memory_entries SET
               content=?, metadata_json=?, last_accessed_at=?,
               access_count=?, retention=?, is_archived=?, is_important=?, summary=?
               WHERE memory_id=?""",
            (
                entry.content,
                json.dumps(entry.metadata, ensure_ascii=False),
                entry.last_accessed_at.isoformat(),
                entry.access_count,
                entry.retention,
                1 if entry.is_archived else 0,
                1 if entry.is_important else 0,
                entry.summary,
                entry.memory_id,
            ),
        )
        self._db.commit()

        # 同步 ChromaDB
        if entry.level.use_vector:
            self._chroma.delete(entry.memory_id)
            self._chroma.store(
                memory_id=entry.memory_id,
                text=entry.content,
                level=entry.level.value,
                scope_id=entry.scope_id,
                metadata=entry.metadata,
            )

    def find_by_id(self, memory_id: str) -> MemoryEntry | None:
        row = self._db.execute(
            "SELECT * FROM memory_entries WHERE memory_id=?",
            (memory_id,),
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def find_by_ids(self, memory_ids: list[str]) -> list[MemoryEntry]:
        if not memory_ids:
            return []
        placeholders = ",".join("?" * len(memory_ids))
        rows = self._db.execute(
            f"SELECT * FROM memory_entries WHERE memory_id IN ({placeholders})",
            tuple(memory_ids),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows if r]

    def find_by_scope(self, level: MemoryLevel, scope_id: str) -> list[MemoryEntry]:
        rows = self._db.execute(
            "SELECT * FROM memory_entries WHERE level=? AND scope_id=? ORDER BY last_accessed_at DESC",
            (level.value, scope_id),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def find_all(
        self,
        level: str | None = None,
        scope_id: str | None = None,
        is_archived: bool | None = None,
        retention_min: float | None = None,
        retention_max: float | None = None,
        keyword: str | None = None,
        sort_by: str = "last_accessed_at",
        sort_desc: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MemoryEntry], int]:
        """分页查询记忆条目，返回 (条目列表, 总数)。

        Args:
            level: 按层级过滤 (session/user/team/project)
            scope_id: 按作用域过滤 (支持 LIKE)
            is_archived: 归档状态过滤
            retention_min/max: 保留率范围过滤
            keyword: 内容关键词搜索
            sort_by: 排序字段 (created_at/last_accessed_at/retention/access_count)
            sort_desc: 是否降序
            page: 页码 (1-based)
            page_size: 每页条数

        Returns:
            (entries, total_count)
        """
        allowed_sort = {
            "created_at", "last_accessed_at", "retention", "access_count", "level", "scope_id"
        }
        if sort_by not in allowed_sort:
            sort_by = "last_accessed_at"
        direction = "DESC" if sort_desc else "ASC"

        conditions = ["1=1"]
        params: list = []

        if level:
            conditions.append("level=?")
            params.append(level)
        if scope_id:
            if "*" in scope_id or "%" in scope_id:
                conditions.append("scope_id LIKE ?")
                params.append(scope_id.replace("*", "%"))
            else:
                conditions.append("scope_id=?")
                params.append(scope_id)
        if is_archived is not None:
            conditions.append("is_archived=?")
            params.append(1 if is_archived else 0)
        if retention_min is not None:
            conditions.append("retention>=?")
            params.append(retention_min)
        if retention_max is not None:
            conditions.append("retention<=?")
            params.append(retention_max)
        if keyword:
            conditions.append("content LIKE ?")
            params.append(f"%{keyword}%")

        where_clause = " AND ".join(conditions)

        # 总数
        count_row = self._db.execute(
            f"SELECT COUNT(*) as cnt FROM memory_entries WHERE {where_clause}",
            tuple(params),
        ).fetchone()
        total = count_row["cnt"] if count_row else 0

        # 分页
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        rows = self._db.execute(
            f"SELECT * FROM memory_entries WHERE {where_clause} "
            f"ORDER BY {sort_by} {direction} LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        ).fetchall()

        return [self._row_to_entry(r) for r in rows], total

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        if query.query_text and query.level and query.level.use_vector:
            return self._vector_search(query)
        return self._sql_search(query)

    def _vector_search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """使用 ChromaDB 语义检索。"""
        results = self._chroma.search(
            query=query.query_text,
            level=query.level.value if query.level else None,
            scope_id=query.scope_id,
            top_k=query.limit * 2,
        )
        memory_ids = [r["id"] for r in results]
        entries = self.find_by_ids(memory_ids)
        # 按 ChromaDB 返回顺序排序
        id_order = {mid: i for i, mid in enumerate(memory_ids)}
        entries.sort(key=lambda e: id_order.get(e.memory_id, 999))
        return entries[: query.limit]

    def _sql_search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """SQL 条件检索。"""
        conditions = ["1=1"]
        params: list = []

        if query.level:
            conditions.append("level=?")
            params.append(query.level.value)
        if query.scope_id:
            conditions.append("scope_id=?")
            params.append(query.scope_id)
        if not query.include_archived:
            conditions.append("is_archived=0")
        if query.is_important is not None:
            conditions.append("is_important=?")
            params.append(1 if query.is_important else 0)
        if query.query_text:
            conditions.append("content LIKE ?")
            params.append(f"%{query.query_text}%")

        rows = self._db.execute(
            f"SELECT * FROM memory_entries WHERE {' AND '.join(conditions)} "
            f"ORDER BY last_accessed_at DESC LIMIT ?",
            (*params, query.limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def find_archivable(self, retention_threshold: float) -> list[MemoryEntry]:
        rows = self._db.execute(
            "SELECT * FROM memory_entries WHERE is_archived=0 AND retention < ?",
            (retention_threshold,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        entry = self.find_by_id(memory_id)
        if not entry:
            return False
        self._db.execute("DELETE FROM memory_entries WHERE memory_id=?", (memory_id,))
        self._db.commit()
        self._chroma.delete(memory_id)
        return True

    def get_stats(self) -> MemoryStats:
        row = self._db.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN is_archived=1 THEN 1 ELSE 0 END) as archived, "
            "AVG(retention) as avg_ret, "
            "SUM(access_count) as total_access "
            "FROM memory_entries",
        ).fetchone()

        by_level = {}
        level_rows = self._db.execute(
            "SELECT level, COUNT(*) as cnt FROM memory_entries GROUP BY level",
        ).fetchall()
        for r in level_rows:
            by_level[r["level"]] = r["cnt"]

        return MemoryStats(
            total_count=row["total"] or 0,
            archived_count=row["archived"] or 0,
            by_level=by_level,
            avg_retention=row["avg_ret"] or 0.0,
            total_access_count=row["total_access"] or 0,
        )

    def _row_to_entry(self, row: sqlite3.Row | None) -> MemoryEntry | None:
        """将 SQLite 行转换为 MemoryEntry 实体。"""
        if row is None:
            return None
        return MemoryEntry(
            memory_id=row["memory_id"],
            level=MemoryLevel(row["level"]),
            scope_id=row["scope_id"],
            content=row["content"],
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]),
            access_count=row["access_count"],
            retention=row["retention"],
            is_archived=bool(row["is_archived"]),
            is_important=bool(row.get("is_important", 0)),
            summary=row["summary"],
        )

    def find_important(self, scope_id: str, limit: int = 20) -> list[MemoryEntry]:
        """查找指定作用域下的重要记忆。"""
        rows = self._db.execute(
            "SELECT * FROM memory_entries WHERE is_important=1 AND scope_id=? "
            "ORDER BY retention DESC, access_count DESC LIMIT ?",
            (scope_id, limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]
