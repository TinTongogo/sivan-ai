"""拓扑反馈数据访问服务 — 封装 TopologyFeedbackLearner 供 API 路由使用。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _get_feedback_learner(db_path: str | Path):
    """懒加载 TopologyFeedbackLearner。"""
    try:
        from domain.orchestration.feedback_learner import TopologyFeedbackLearner
        from infrastructure.persistence.connection import SQLiteConnectionManager
        cm = SQLiteConnectionManager(str(db_path))
        return TopologyFeedbackLearner(cm)
    except Exception:
        return None


def topology_feedback_stats(db_path: str | Path) -> dict[str, Any]:
    """获取拓扑反馈统计。"""
    learner = _get_feedback_learner(db_path)
    if not learner:
        return {"total_records": 0, "avg_satisfaction": 0, "unique_signatures": 0}
    try:
        return learner.get_stats()
    except Exception:
        return {"total_records": 0, "avg_satisfaction": 0, "unique_signatures": 0}


def topology_feedback_list(db_path: str | Path, limit: int = 50) -> list[dict[str, Any]]:
    """列出最近的拓扑反馈记录。"""
    learner = _get_feedback_learner(db_path)
    if not learner:
        return []
    try:
        return learner.list_recent(limit=limit)
    except Exception:
        return []


def topology_feedback_record(
    db_path: str | Path,
    task_signature: str,
    topology: dict[str, Any],
    satisfaction: float,
    execution_id: str = "",
) -> dict[str, Any]:
    """记录一条拓扑反馈。"""
    learner = _get_feedback_learner(db_path)
    if not learner:
        return {"error": "拓扑反馈学习器不可用"}
    try:
        rid = learner.record_outcome(task_signature, topology, satisfaction, execution_id)
        return {"id": rid, "status": "recorded"}
    except Exception as e:
        return {"error": str(e)}
