"""技能仓库 SQLite 实现。

基于现有 SkillLoader 实现 ISkillRepository 接口。
"""

from __future__ import annotations

from typing import Any

from domain.skill.repository import ISkillRepository
from infrastructure.persistence.connection import SQLiteConnectionManager


class Skill:
    """技能数据类。"""

    def __init__(
        self,
        skill_id: str,
        name: str,
        display_name: str,
        description: str,
        content: str,
        category: str,
        argument_hint: str = "",
        allowed_tools: list[str] | None = None,
    ) -> None:
        self.skill_id = skill_id
        self.name = name
        self.display_name = display_name
        self.description = description
        self.content = content
        self.category = category
        self.argument_hint = argument_hint
        self.allowed_tools = allowed_tools or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "content": self.content,
            "category": self.category,
            "argument_hint": self.argument_hint,
            "allowed_tools": self.allowed_tools,
        }


class SkillRepository(ISkillRepository):
    """基于 SQLite 的技能仓库。"""

    def __init__(self, connection_manager: SQLiteConnectionManager) -> None:
        self._db = connection_manager
        self._skills: dict[str, Skill] = {}
        self._init_tables()
        self._load_all()

    def _init_tables(self) -> None:
        pass  # schema 由 Alembic 管理

    def _load_all(self) -> None:
        self._skills.clear()
        rows = self._db.execute(
            "SELECT * FROM skills WHERE status = 'active'"
        ).fetchall()
        for row in rows:
            skill = self._row_to_skill(row)
            self._skills[skill.skill_id] = skill

    def _row_to_skill(self, row) -> Skill:
        import json
        allowed_tools_str = row["allowed_tools"]
        allowed_tools: list[str] = []
        if allowed_tools_str:
            try:
                allowed_tools = json.loads(allowed_tools_str)
                if not isinstance(allowed_tools, list):
                    allowed_tools = []
            except (json.JSONDecodeError, TypeError):
                if "," in allowed_tools_str:
                    allowed_tools = [t.strip() for t in allowed_tools_str.split(",") if t.strip()]
                else:
                    allowed_tools = [t.strip() for t in allowed_tools_str.split() if t.strip()]

        return Skill(
            skill_id=row["skill_id"],
            name=row["name"],
            display_name=row["display_name"] or row["name"],
            description=row["description"],
            content=row["content"],
            category=row["category"],
            argument_hint=row["argument_hint"] or "",
            allowed_tools=allowed_tools,
        )

    def find_by_id(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def find_all(self) -> dict[str, Skill]:
        return dict(self._skills)

    def list_all(self) -> list[str]:
        return list(self._skills.keys())

    def reload_all(self) -> None:
        self._load_all()
