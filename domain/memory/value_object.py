"""记忆领域值对象。

定义 MemoryQuery、MemoryStats 等不可变查询/统计对象。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.common.value_object import MemoryLevel, PageRequest


@dataclass
class MemoryQuery:
    """记忆检索查询参数。"""
    query_text: str = ""
    level: MemoryLevel | None = None
    scope_id: str | None = None
    limit: int = 10
    min_retention: float = 0.3
    include_archived: bool = False
    is_important: bool | None = None  # None=不过滤, True=仅重要, False=仅非重要
    page: PageRequest | None = None


@dataclass
class MemoryStats:
    """记忆统计。"""
    total_count: int = 0
    archived_count: int = 0
    by_level: dict[str, int] = field(default_factory=dict)
    avg_retention: float = 0.0
    total_access_count: int = 0


@dataclass
class MemorySummary:
    """记忆摘要 (用于归档后的紧凑表示)。"""
    memory_id: str
    scope_id: str
    summary: str
    original_length: int
    created_at: str
    last_accessed_at: str
    access_count: int
    retention: float
