"""本能模板仓库 SQLite 实现。

存储已验证的任务 → 编排拓扑映射，支持快速匹配和置信度更新。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from domain.memory.instinct import InstinctPattern
from infrastructure.persistence.connection import SQLiteConnectionManager


class InstinctRepository:
    """本能模板仓库。

    直接使用 SQLite 存储（层级单一，无需向量），
    通过 task_type + task_signature 进行精确和模糊匹配。
    """

    def __init__(self, connection_manager: SQLiteConnectionManager) -> None:
        self._db = connection_manager

    def _row_to_pattern(self, row: Any) -> InstinctPattern:
        return InstinctPattern(
            pattern_id=row["pattern_id"],
            task_type=row["task_type"],
            task_signature=row["task_signature"],
            topology_json=row["topology_json"],
            success_count=row["success_count"],
            total_count=row["total_count"],
            confidence=row["confidence"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.now(),
        )

    def save(self, pattern: InstinctPattern) -> str:
        """保存本能模板。"""
        if not pattern.pattern_id:
            pattern.pattern_id = uuid.uuid4().hex[:12]
        pattern.updated_at = datetime.now()

        self._db.execute(
            """INSERT OR REPLACE INTO instinct_patterns
               (pattern_id, task_type, task_signature, topology_json,
                success_count, total_count, confidence, is_active,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pattern.pattern_id,
                pattern.task_type,
                pattern.task_signature,
                pattern.topology_json,
                pattern.success_count,
                pattern.total_count,
                pattern.confidence,
                1 if pattern.is_active else 0,
                pattern.created_at.isoformat() if hasattr(pattern.created_at, "isoformat") else pattern.created_at,
                pattern.updated_at.isoformat() if hasattr(pattern.updated_at, "isoformat") else pattern.updated_at,
            ),
        )
        self._db.commit()
        return pattern.pattern_id

    def update(self, pattern: InstinctPattern) -> None:
        """更新本能模板（置信度、计数等）。"""
        pattern.updated_at = datetime.now()
        self._db.execute(
            """UPDATE instinct_patterns SET
               task_type=?, task_signature=?, topology_json=?,
               success_count=?, total_count=?, confidence=?, is_active=?,
               updated_at=?
               WHERE pattern_id=?""",
            (
                pattern.task_type,
                pattern.task_signature,
                pattern.topology_json,
                pattern.success_count,
                pattern.total_count,
                pattern.confidence,
                1 if pattern.is_active else 0,
                pattern.updated_at.isoformat() if hasattr(pattern.updated_at, "isoformat") else pattern.updated_at,
                pattern.pattern_id,
            ),
        )
        self._db.commit()

    def find_by_id(self, pattern_id: str) -> InstinctPattern | None:
        """按 ID 查找。"""
        row = self._db.execute(
            "SELECT * FROM instinct_patterns WHERE pattern_id=?",
            (pattern_id,),
        ).fetchone()
        return self._row_to_pattern(row) if row else None

    def find_matching(self, task_type: str, task_signature: str) -> InstinctPattern | None:
        """查找匹配的本能模板。

        匹配策略：
        1. 优先精确匹配 task_type + task_signature
        2. 回退到 task_type 精确匹配 + task_signature 前缀匹配
        3. 仅返回活跃 (is_active=1) 的模板

        Args:
            task_type: 任务类型
            task_signature: 归一化任务特征

        Returns:
            InstinctPattern | None: 置信度最高的匹配模板
        """
        # 精确匹配
        row = self._db.execute(
            "SELECT * FROM instinct_patterns WHERE is_active=1 AND task_type=? AND task_signature=?",
            (task_type, task_signature),
        ).fetchone()
        if row:
            return self._row_to_pattern(row)

        # 模糊匹配：同 task_type 下，task_signature 前缀匹配
        rows = self._db.execute(
            "SELECT * FROM instinct_patterns WHERE is_active=1 AND task_type=? ORDER BY confidence DESC",
            (task_type,),
        ).fetchall()
        if not rows:
            return None

        # 取第一个匹配即可
        return self._row_to_pattern(rows[0])

    def find_active(self) -> list[InstinctPattern]:
        """列出所有已激活的本能模板。"""
        rows = self._db.execute(
            "SELECT * FROM instinct_patterns WHERE is_active=1 ORDER BY confidence DESC",
        ).fetchall()
        return [self._row_to_pattern(r) for r in rows]

    def find_all(self, page: int = 1, page_size: int = 20) -> tuple[list[InstinctPattern], int]:
        """分页列出所有模板。"""
        total_row = self._db.execute("SELECT COUNT(*) as cnt FROM instinct_patterns").fetchone()
        total = total_row["cnt"] if total_row else 0

        offset = (page - 1) * page_size
        rows = self._db.execute(
            "SELECT * FROM instinct_patterns ORDER BY confidence DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        ).fetchall()
        return [self._row_to_pattern(r) for r in rows], total

    def delete(self, pattern_id: str) -> bool:
        """删除模板。"""
        self._db.execute("DELETE FROM instinct_patterns WHERE pattern_id=?", (pattern_id,))
        self._db.commit()
        return True
