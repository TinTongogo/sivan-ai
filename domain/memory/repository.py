"""记忆仓库接口。

定义 IMemoryRepository 抽象接口，具体实现由基础设施层提供。
"""

from abc import ABC, abstractmethod

from domain.common.value_object import MemoryLevel
from domain.memory.entity import MemoryEntry
from domain.memory.value_object import MemoryQuery, MemoryStats


class IMemoryRepository(ABC):
    """记忆仓库接口 (Repository 模式)。"""

    @abstractmethod
    def save(self, entry: MemoryEntry) -> str:
        """保存记忆条目，返回 memory_id。"""
        ...

    @abstractmethod
    def update(self, entry: MemoryEntry) -> None:
        """更新记忆条目。"""
        ...

    @abstractmethod
    def find_by_id(self, memory_id: str) -> MemoryEntry | None:
        """按 ID 查找。"""
        ...

    @abstractmethod
    def find_by_ids(self, memory_ids: list[str]) -> list[MemoryEntry]:
        """批量查找。"""
        ...

    @abstractmethod
    def find_by_scope(self, level: MemoryLevel, scope_id: str) -> list[MemoryEntry]:
        """按层级和作用域查找。"""
        ...

    @abstractmethod
    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """综合检索。"""
        ...

    @abstractmethod
    def find_archivable(self, retention_threshold: float) -> list[MemoryEntry]:
        """查找需要归档的低保留率记忆。"""
        ...

    @abstractmethod
    def find_important(self, scope_id: str, limit: int = 20) -> list[MemoryEntry]:
        """查找指定作用域下的重要记忆。"""
        ...

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """删除记忆条目。"""
        ...

    @abstractmethod
    def get_stats(self) -> MemoryStats:
        """获取统计信息。"""
        ...
