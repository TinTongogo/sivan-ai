"""项目仓库 SQLite 实现。"""

from __future__ import annotations

from typing import Any

from domain.project.repository import IProjectRepository
from infrastructure.persistence.connection import SQLiteConnectionManager


class ProjectRepository(IProjectRepository):
    """基于 SQLiteConnectionManager 的项目仓库。"""

    def __init__(self, connection_manager: SQLiteConnectionManager) -> None:
        self._db = connection_manager

    def _row(self, row: Any) -> dict[str, Any]:
        return dict(row) if row else {}

    def find_by_id(self, project_id: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT * FROM projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        return self._row(row) if row else None

    def find_all(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM projects ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def create(self, project: dict[str, Any]) -> dict[str, Any]:
        import uuid
        pid = project.get("project_id") or uuid.uuid4().hex[:12]
        self._db.execute(
            "INSERT INTO projects (project_id, name, description, status, created_by) VALUES (?, ?, ?, ?, ?)",
            (pid, project.get("name", "未命名"), project.get("description", ""),
             project.get("status", "active"), project.get("created_by", "")),
        )
        return self.find_by_id(pid) or {}

    def update(self, project_id: str, data: dict[str, Any]) -> bool:
        fields = []
        params = []
        for key in ("name", "description", "status"):
            if key in data:
                fields.append(f"{key} = ?")
                params.append(data[key])
        if not fields:
            return False
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(project_id)
        self._db.execute(
            f"UPDATE projects SET {', '.join(fields)} WHERE project_id = ?",
            tuple(params),
        )
        return True

    def delete(self, project_id: str) -> bool:
        self._db.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        return True

    def assign_kb(self, project_id: str, kb_name: str) -> bool:
        self._db.execute(
            "INSERT OR IGNORE INTO kb_project_assignments (kb_name, project_id) VALUES (?, ?)",
            (kb_name, project_id),
        )
        return True

    def unassign_kb(self, project_id: str, kb_name: str) -> bool:
        self._db.execute(
            "DELETE FROM kb_project_assignments WHERE kb_name = ? AND project_id = ?",
            (kb_name, project_id),
        )
        return True

    def get_assigned_kbs(self, project_id: str) -> list[str]:
        rows = self._db.execute(
            "SELECT kb_name FROM kb_project_assignments WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        return [r["kb_name"] for r in rows]

    def get_project_by_kb(self, kb_name: str) -> list[str]:
        rows = self._db.execute(
            "SELECT project_id FROM kb_project_assignments WHERE kb_name = ?",
            (kb_name,),
        ).fetchall()
        return [r["project_id"] for r in rows]
