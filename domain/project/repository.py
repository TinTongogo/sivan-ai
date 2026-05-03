"""项目仓库接口。"""

from abc import ABC, abstractmethod
from typing import Any


class IProjectRepository(ABC):
    """项目仓库接口。"""

    @abstractmethod
    def find_by_id(self, project_id: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def find_all(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def create(self, project: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def update(self, project_id: str, data: dict[str, Any]) -> bool:
        ...

    @abstractmethod
    def delete(self, project_id: str) -> bool:
        ...

    @abstractmethod
    def assign_kb(self, project_id: str, kb_name: str) -> bool:
        ...

    @abstractmethod
    def unassign_kb(self, project_id: str, kb_name: str) -> bool:
        ...

    @abstractmethod
    def get_assigned_kbs(self, project_id: str) -> list[str]:
        ...

    @abstractmethod
    def get_project_by_kb(self, kb_name: str) -> list[str]:
        ...
