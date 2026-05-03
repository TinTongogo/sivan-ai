"""技能应用服务。

组合技能仓储，提供技能管理用例。
"""

from __future__ import annotations

from typing import Any

from domain.skill.repository import ISkillRepository


class SkillService:
    """技能应用服务。"""

    def __init__(self, skill_repo: ISkillRepository) -> None:
        self._repo = skill_repo

    def list_skills(self) -> list[dict[str, Any]]:
        skills = self._repo.find_all()
        return [
            {
                "skill_id": sid,
                "name": skill.name,
                "display_name": skill.display_name,
                "description": skill.description,
                "category": skill.category,
            }
            for sid, skill in skills.items()
        ]

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        skill = self._repo.find_by_id(skill_id)
        return skill.to_dict() if skill else None

    def reload_all(self) -> None:
        self._repo.reload_all()
