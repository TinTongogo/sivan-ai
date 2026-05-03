"""契约仓库接口。"""

from abc import ABC, abstractmethod
from typing import Any


class IContractRepository(ABC):
    """契约仓库接口。"""

    @abstractmethod
    def create(self, contract_type: str, content: dict[str, Any], created_by: str) -> str:
        """创建契约。"""
        ...

    @abstractmethod
    def find_by_id(self, contract_id: str) -> dict[str, Any] | None:
        """按 ID 查找契约。"""
        ...

    @abstractmethod
    def update(self, contract_id: str, updates: dict[str, Any]) -> bool:
        """更新契约。"""
        ...

    @abstractmethod
    def find(
        self,
        contract_type: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """查找契约。"""
        ...

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        ...
