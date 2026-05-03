"""智能体仓库接口。"""

from abc import ABC, abstractmethod
from typing import Any


class IAgentRepository(ABC):
    """智能体仓库接口。"""

    @abstractmethod
    def find_by_id(self, agent_id: str) -> dict[str, Any] | None:
        """按 ID 查找智能体配置。"""
        ...

    @abstractmethod
    def find_all_active(self) -> dict[str, Any]:
        """获取所有活跃智能体 {agent_id: config_dict}。"""
        ...

    @abstractmethod
    def reload(self, agent_id: str) -> bool:
        """重新加载指定智能体。"""
        ...

    @abstractmethod
    def reload_all(self) -> None:
        """重新加载所有智能体。"""
        ...

    @abstractmethod
    def execute(self, agent_id: str, task: str, context: dict | None = None) -> str:
        """执行智能体任务。"""
        ...

    @abstractmethod
    def list_all(self) -> list[str]:
        """列出所有活跃智能体 ID。"""
        ...
