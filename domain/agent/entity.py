"""智能体领域实体。

定义 AgentConfig、Agent 等核心实体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentConfig:
    """智能体配置值对象。"""
    agent_id: str
    display_name: str
    description: str
    system_prompt: str
    craft_declaration: str = ""
    tools: list[str] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)


class Agent:
    """智能体实体。

    封装智能体配置、技能、能力等核心属性。
    TODO: Phase 4 中集成 GenericAgent 的执行逻辑。
    """

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._skills: dict[str, Any] = {}

    @property
    def agent_id(self) -> str:
        return self._config.agent_id

    @property
    def display_name(self) -> str:
        return self._config.display_name

    @property
    def description(self) -> str:
        return self._config.description

    @property
    def system_prompt(self) -> str:
        return self._config.system_prompt

    @property
    def config(self) -> AgentConfig:
        return self._config

    @property
    def skill_ids(self) -> list[str]:
        return list(self._config.skill_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "description": self.description,
            "skills": self.skill_ids,
            "tools": list(self._config.tools),
        }
