"""路由领域实体。

从 core/routing_db.py 提取的核心数据类。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class RoutingStrategy(str, Enum):
    """路由策略枚举。"""
    SEMANTIC = "semantic"
    ML = "ml"
    CONTEXT_AWARE = "context_aware"
    ADAPTIVE = "adaptive"
    EXPLICIT = "explicit"
    FALLBACK = "fallback"


class RoutingStatus(str, Enum):
    """路由状态枚举。"""
    SUCCESS = "success"
    FAILED = "failed"
    NO_MATCH = "no_match"
    ERROR = "error"
    TIMEOUT = "timeout"


class FeedbackType(str, Enum):
    """反馈类型枚举。"""
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"
    UNSURE = "unsure"


@dataclass
class RoutingDecision:
    """路由决策。"""
    id: int | None = None
    decision_id: str | None = None
    task_description: str = ""
    task_hash: str | None = None
    selected_agent: str | None = None
    routing_strategy: RoutingStrategy = RoutingStrategy.SEMANTIC
    status: RoutingStatus = RoutingStatus.SUCCESS
    confidence_score: float | None = None
    execution_time_ms: float | None = None
    context_json: str | None = None
    created_at: str | None = None
    user_id: str | None = None
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["routing_strategy"] = self.routing_strategy.value
        data["status"] = self.status.value
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingDecision:
        data = data.copy()
        data["routing_strategy"] = RoutingStrategy(data["routing_strategy"])
        data["status"] = RoutingStatus(data["status"])
        return cls(**data)


@dataclass
class CandidateScore:
    """候选智能体得分。"""
    id: int | None = None
    decision_id: int | None = None
    agent_name: str = ""
    score: float = 0.0
    rank: int = 0
    features_json: str | None = None


@dataclass
class UserFeedback:
    """用户反馈。"""
    id: int | None = None
    decision_id: int | None = None
    feedback_type: FeedbackType = FeedbackType.CORRECT
    corrected_agent: str | None = None
    feedback_text: str | None = None
    rating: int | None = None
    created_at: str | None = None


@dataclass
class AgentPerformance:
    """智能体性能统计。"""
    agent_name: str = ""
    total_tasks: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_confidence: float | None = None
    avg_execution_time_ms: float | None = None
    feedback_correct_rate: float | None = None
    last_updated: str | None = None
