"""智能体基类 — 从 core/agents 迁移。

模板方法模式 + 装饰器模式。
使用 domain/task/entity.py 的 Task/TaskResult。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from domain.task.entity import Task, TaskResult


class IAgent(ABC):
    """智能体接口。"""

    @abstractmethod
    def execute(self, task: Task) -> TaskResult:
        ...

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        ...

    @abstractmethod
    def get_requirements(self) -> dict[str, Any]:
        ...


class BaseAgent(IAgent, ABC):
    """基础智能体 — 模板方法模式。"""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self.skills = config.get("skills", [])
        self.tool_permissions = config.get("tool_permissions", [])

    def execute(self, task: Task) -> TaskResult:
        """模板方法：定义执行流程。"""
        start_time = datetime.now()
        try:
            self._validate_task(task)
            context = self._preprocess_context(task.context)
            output = self._execute_core(task.description, context)
            processed_output = self._postprocess_output(output)
            self._validate_output(processed_output)
            execution_time = (datetime.now() - start_time).total_seconds()
            return TaskResult(
                task_id=task.task_id,
                agent_name=self.name,
                output=processed_output,
                status="success",
                execution_time=execution_time,
                created_at=datetime.now(),
            )
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return TaskResult(
                task_id=task.task_id,
                agent_name=self.name,
                output={"error": str(e)},
                status="failed",
                execution_time=execution_time,
                created_at=datetime.now(),
            )

    @abstractmethod
    def _execute_core(self, task_description: str, context: dict[str, Any]) -> Any:
        ...

    def _validate_task(self, task: Task) -> None:
        if not task.description:
            raise ValueError("任务描述不能为空")

    def _preprocess_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return context or {}

    def _postprocess_output(self, output: Any) -> Any:
        return output

    def _validate_output(self, output: Any) -> None:
        pass

    def get_capabilities(self) -> list[str]:
        return self.skills

    def get_requirements(self) -> dict[str, Any]:
        return {"tool_permissions": self.tool_permissions, "skills": self.skills}


class AgentDecorator(IAgent):
    """智能体装饰器基类。"""

    def __init__(self, agent: IAgent) -> None:
        self._agent = agent

    def execute(self, task: Task) -> TaskResult:
        return self._agent.execute(task)

    def get_capabilities(self) -> list[str]:
        return self._agent.get_capabilities()

    def get_requirements(self) -> dict[str, Any]:
        return self._agent.get_requirements()
