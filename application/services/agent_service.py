"""智能体应用服务。

组合领域实体与基础设施，提供智能体管理用例。
"""

from __future__ import annotations

from typing import Any

from domain.agent.repository import IAgentRepository


class AgentService:
    """智能体应用服务。"""

    def __init__(self, agent_repo: IAgentRepository) -> None:
        self._repo = agent_repo

    def list_agents(self) -> list[dict[str, Any]]:
        agents = self._repo.find_all_active()
        result = []
        for agent_id, agent in agents.items():
            result.append({
                "agent_id": agent_id,
                "display_name": getattr(agent, "agent_config", None)
                and agent.agent_config.display_name or agent_id,
                "description": getattr(agent, "agent_config", None)
                and agent.agent_config.description or "",
            })
        return result

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        return self._repo.find_by_id(agent_id)

    def execute(self, agent_id: str, task: str, context: dict | None = None) -> str:
        return self._repo.execute(agent_id, task, context)

    def reload(self, agent_id: str) -> bool:
        return self._repo.reload(agent_id)

    def reload_all(self) -> None:
        self._repo.reload_all()
