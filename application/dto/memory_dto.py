"""记忆相关数据传输对象 (DTO)。

用于应用层与接口层之间的数据传输。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MemoryEntryDTO:
    """记忆条目的 DTO。"""
    memory_id: str
    level: str
    scope_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    last_accessed_at: str = ""
    access_count: int = 0
    retention: float = 1.0
    is_archived: bool = False
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["created_at"] = str(result["created_at"])
        result["last_accessed_at"] = str(result["last_accessed_at"])
        return result


@dataclass
class StoreMemoryDTO:
    """存储记忆的请求 DTO。"""
    content: str
    level: str = "session"
    scope_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchMemoryDTO:
    """搜索记忆的请求 DTO。"""
    query: str = ""
    level: str | None = None
    scope_id: str | None = None
    limit: int = 10
    min_retention: float = 0.3


@dataclass
class MemoryContextDTO:
    """上下文注入的请求 DTO。"""
    query: str = ""
    scope_ids: dict[str, str] = field(default_factory=dict)
    top_k: int = 5
