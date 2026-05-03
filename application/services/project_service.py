"""项目应用服务。"""

from __future__ import annotations

from typing import Any

from domain.project.repository import IProjectRepository


class ProjectService:
    """项目 CRUD + KB 分配。"""

    def __init__(self, repo: IProjectRepository) -> None:
        self._repo = repo

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        return self._repo.find_by_id(project_id)

    def list_projects(self) -> list[dict[str, Any]]:
        return self._repo.find_all()

    def create_project(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._repo.create({
            "name": data.get("name", "未命名"),
            "description": data.get("description", ""),
            "status": data.get("status", "active"),
            "created_by": data.get("created_by", ""),
        })

    def update_project(self, project_id: str, data: dict[str, Any]) -> bool:
        return self._repo.update(project_id, data)

    def delete_project(self, project_id: str) -> bool:
        return self._repo.delete(project_id)

    def assign_kb(self, project_id: str, kb_name: str) -> bool:
        return self._repo.assign_kb(project_id, kb_name)

    def unassign_kb(self, project_id: str, kb_name: str) -> bool:
        return self._repo.unassign_kb(project_id, kb_name)

    def get_assigned_kbs(self, project_id: str) -> list[str]:
        return self._repo.get_assigned_kbs(project_id)

    def get_kb_names_for_project(self, kb_service: Any, project_id: str) -> list[str]:
        """获取项目下所有可用知识库名称。"""
        assigned = self._repo.get_assigned_kbs(project_id)
        if assigned:
            return assigned
        # 未分配 KB 时返回所有全局 KB
        all_kbs = kb_service.list_knowledge_bases() if hasattr(kb_service, "list_knowledge_bases") else []
        return [kb["kb_name"] for kb in all_kbs] if isinstance(all_kbs, list) else []
