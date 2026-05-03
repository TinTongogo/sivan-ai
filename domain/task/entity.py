"""任务领域实体。

定义 Task、TaskResult 等核心任务实体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Task:
    """任务实体。"""
    task_id: str
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    created_by: str = "system"
    priority: int = 5


@dataclass
class TaskResult:
    """任务结果实体。"""
    task_id: str
    agent_name: str
    output: Any = None
    status: str = "success"  # success, failed, partial
    execution_time: float = 0.0
    created_at: datetime | None = None
    error: str | None = None
