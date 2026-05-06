"""智能体仓库 SQLite 实现。

基于现有 AgentLoader 实现 IAgentRepository 接口。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from domain.agent.repository import IAgentRepository
from domain.task.entity import Task
from infrastructure.agents.generic_agent import AgentConfig, GenericAgent
from infrastructure.agents.orchestrator import OrchestratorAgent
from infrastructure.persistence.connection import SQLiteConnectionManager

logger = logging.getLogger("sivan.agent_repo")


class AgentRepository(IAgentRepository):
    """基于 SQLite + GenericAgent 的智能体仓库。"""

    def __init__(self, connection_manager: SQLiteConnectionManager,
                 kb_service=None) -> None:
        self._db = connection_manager
        self._kb_service = kb_service
        self._GenericAgent = GenericAgent
        self._OrchestratorAgent = OrchestratorAgent
        self._AgentConfig = AgentConfig
        self._agents: dict[str, Any] = {}
        self._init_tables()
        self._load_all()

    def _init_tables(self) -> None:
        pass  # schema 由 Alembic 管理

    def _load_all(self) -> None:
        self._agents.clear()
        rows = self._db.execute(
            "SELECT * FROM agents WHERE status = 'active'"
        ).fetchall()
        for row in rows:
            agent_id = row["agent_id"]
            config = self._row_to_config(row)
            if agent_id == "orchestrator":
                agent = self._OrchestratorAgent(config, self._db.connection)
            else:
                agent = self._GenericAgent(config, self._db.connection, kb_service=self._kb_service)
            self._agents[agent_id] = agent

    def _row_to_config(self, row) -> Any:
        def _safe_json(val: str | None) -> list:
            if not val or not val.strip():
                return []
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return []
        return self._AgentConfig(
            agent_id=row["agent_id"],
            display_name=row["display_name"],
            description=row["description"] or "",
            system_prompt=row["system_prompt"],
            craft_declaration=row["craft_declaration"] or "",
            tools=_safe_json(row["tools"]),
            skill_ids=_safe_json(row["skill_ids"]),
            agent_type=row.get("agent_type", "user"),
        )

    def find_by_id(self, agent_id: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT * FROM agents WHERE agent_id = ? AND status = 'active'",
            (agent_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def find_all_active(self) -> dict[str, Any]:
        return {aid: agent for aid, agent in self._agents.items()}

    def get_agent_type(self, agent_id: str) -> str | None:
        """获取智能体类型（user / dynamic）。"""
        agent = self._agents.get(agent_id)
        if agent and hasattr(agent, "agent_config"):
            return agent.agent_config.agent_type
        return None

    def reload(self, agent_id: str) -> bool:
        row = self._db.execute(
            "SELECT * FROM agents WHERE agent_id = ? AND status = 'active'",
            (agent_id,),
        ).fetchone()
        if not row:
            return False
        config = self._row_to_config(row)
        if agent_id == "orchestrator":
            self._agents[agent_id] = self._OrchestratorAgent(config, self._db.connection)
        else:
            self._agents[agent_id] = self._GenericAgent(config, self._db.connection, kb_service=self._kb_service)
        return True

    def reload_all(self) -> None:
        self._load_all()

    def execute(self, agent_id: str, task: str, context: dict | None = None) -> str:
        agent = self._agents.get(agent_id)
        if not agent:
            # 懒加载：不在缓存中时尝试从 DB 加载（重启后首次调用动态 agent）
            if not self.reload(agent_id):
                return f"错误: 智能体 {agent_id} 不存在或未激活"
            agent = self._agents.get(agent_id)

        task_obj = Task(
            task_id=f"{agent_id}-{id(task)}",
            description=task,
            context=context or {},
            created_at=datetime.now(),
            created_by="agent_repository",
        )
        result = agent.execute(task_obj)
        return result.output if result.status == "success" else f"任务失败: {result.output}"

    def list_all(self) -> list[str]:
        return list(self._agents.keys())
