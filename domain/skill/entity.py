"""技能领域实体。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Skill:
    """技能实体。"""
    skill_id: str
    name: str
    display_name: str
    description: str
    content: str
    category: str
    argument_hint: str = ""
    allowed_tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "content": self.content,
            "category": self.category,
            "argument_hint": self.argument_hint,
            "allowed_tools": list(self.allowed_tools),
        }
