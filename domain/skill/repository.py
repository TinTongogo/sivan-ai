"""技能仓库接口。"""

from abc import ABC, abstractmethod
from typing import Any


class ISkillRepository(ABC):
    """技能仓库接口。"""

    @abstractmethod
    def find_by_id(self, skill_id: str) -> Any | None:
        """按 ID 查找技能。"""
        ...

    @abstractmethod
    def find_all(self) -> dict[str, Any]:
        """获取所有技能 {skill_id: skill}。"""
        ...

    @abstractmethod
    def list_all(self) -> list[str]:
        """列出所有技能 ID。"""
        ...

    @abstractmethod
    def reload_all(self) -> None:
        """重新加载所有技能。"""
        ...
