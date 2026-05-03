"""记忆应用服务。

组合领域层实体与基础设施层实现，提供完整记忆管理功能：
- 记忆 CRUD
- 语义检索 (ChromaDB)
- 遗忘曲线计算与归档
- 上下文注入
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from domain.common.interfaces import IContextInjector
from domain.common.value_object import MemoryLevel
from domain.memory.entity import MemoryEntry
from domain.memory.repository import IMemoryRepository
from domain.memory.value_object import MemoryQuery, MemoryStats


class MemoryService:
    """记忆应用服务。

    职责：
    - 记忆的读写与检索
    - 遗忘曲线自动计算
    - 低频记忆归档
    - 上下文注入
    """

    def __init__(
        self,
        memory_repo: IMemoryRepository,
        context_injector: IContextInjector,
    ) -> None:
        self._repo = memory_repo
        self._context_injector = context_injector

    # --- CRUD ---

    def store(
        self,
        content: str,
        level: str,
        scope_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """存储一条记忆。"""
        memory_level = MemoryLevel(level)
        entry = MemoryEntry(
            memory_id="",
            level=memory_level,
            scope_id=scope_id,
            content=content,
            metadata=metadata or {},
        )
        entry.calculate_retention()
        return self._repo.save(entry)

    def get(self, memory_id: str) -> MemoryEntry | None:
        """获取并访问一条记忆 (重置衰减)。"""
        entry = self._repo.find_by_id(memory_id)
        if entry:
            entry.access()
            self._repo.update(entry)
        return entry

    def delete(self, memory_id: str) -> bool:
        """删除记忆。"""
        return self._repo.delete(memory_id)

    def update(
        self, memory_id: str, content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry | None:
        """更新记忆内容/元数据。"""
        entry = self._repo.find_by_id(memory_id)
        if not entry:
            return None
        if content is not None:
            entry.content = content
        if metadata is not None:
            entry.metadata = metadata
        self._repo.update(entry)
        return entry

    def list_memories(
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
        """分页列出记忆，返回 (条目列表, 总数)。"""
        return self._repo.find_all(
            level=level, scope_id=scope_id, is_archived=is_archived,
            retention_min=retention_min, retention_max=retention_max,
            keyword=keyword, sort_by=sort_by, sort_desc=sort_desc,
            page=page, page_size=page_size,
        )

    # --- 检索 ---

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """搜索记忆 (语义 + 条件混合检索)。"""
        entries = self._repo.search(query)

        # 计算每条记忆的当前保留率
        now = datetime.now()
        for entry in entries:
            entry.calculate_retention(now)

        # 过滤低保留率
        if not query.include_archived:
            entries = [e for e in entries if e.retention >= query.min_retention]

        return entries[: query.limit]

    def find_by_scope(self, level: str, scope_id: str) -> list[MemoryEntry]:
        """按作用域查找。"""
        return self._repo.find_by_scope(MemoryLevel(level), scope_id)

    # --- 遗忘曲线 ---

    def calculate_retention(
        self, memory_id: str, now: datetime | None = None
    ) -> float | None:
        """计算指定记忆的当前保留率。"""
        entry = self._repo.find_by_id(memory_id)
        if not entry:
            return None
        retention = entry.calculate_retention(now)
        self._repo.update(entry)
        return retention

    def get_retention_status(self, level: str) -> list[dict[str, Any]]:
        """获取某层级所有记忆的保留率状态。"""
        memory_level = MemoryLevel(level)
        all_entries = self._repo.find_by_scope(memory_level, "*")
        now = datetime.now()
        results = []
        for entry in all_entries:
            retention = entry.calculate_retention(now)
            results.append({
                "memory_id": entry.memory_id,
                "content_preview": entry.content[:100],
                "retention": retention,
                "access_count": entry.access_count,
                "level": entry.level.value,
                "scope_id": entry.scope_id,
            })
        return results

    # --- 归档 ---

    def check_archive(self, threshold: float = 0.15) -> list[MemoryEntry]:
        """查找并归档低保留率记忆。

        Args:
            threshold: 归档保留率阈值

        Returns:
            已归档的记忆列表
        """
        entries = self._repo.find_archivable(threshold)
        archived = []
        for entry in entries:
            entry.is_archived = True
            entry.summary = entry.content[:200]  # 截取前 200 字作为摘要
            self._repo.update(entry)
            archived.append(entry)
        return archived

    def unarchive(self, memory_id: str) -> MemoryEntry | None:
        """恢复已归档记忆。"""
        entry = self._repo.find_by_id(memory_id)
        if entry and entry.is_archived:
            entry.is_archived = False
            entry.access()  # 重置保留率
            self._repo.update(entry)
        return entry

    # --- 统计 ---

    def get_stats(self) -> MemoryStats:
        """获取记忆统计。"""
        return self._repo.get_stats()

    # --- 上下文注入 ---

    def build_context(
        self,
        query: str,
        scope_ids: dict[MemoryLevel, str] | None = None,
        top_k: int = 5,
    ) -> str:
        """构建记忆上下文文本。"""
        return self._context_injector.build_context(query, scope_ids, top_k)

    def inject_to_prompt(self, system_prompt: str, memory_context: str) -> str:
        """注入记忆上下文到 system_prompt。"""
        return self._context_injector.inject_to_prompt(system_prompt, memory_context)
