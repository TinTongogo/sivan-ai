"""路由仓库 SQLite 实现。

实现路由决策的持久化存储。
"""

from __future__ import annotations

import hashlib
from typing import Any

from domain.routing.entity import (
    CandidateScore,
    RoutingDecision,
    RoutingStatus,
    RoutingStrategy,
    UserFeedback,
)
from infrastructure.persistence.connection import SQLiteConnectionManager


class RoutingRepository:
    """基于 SQLite 的路由决策仓库。"""

    def __init__(self, connection_manager: SQLiteConnectionManager) -> None:
        self._db = connection_manager
        self._init_tables()

    def _init_tables(self) -> None:
        pass  # schema 由 Alembic 管理

    def record_decision(
        self,
        decision: RoutingDecision,
        candidates: list[CandidateScore] | None = None,
    ) -> int:
        if not decision.task_hash:
            decision.task_hash = hashlib.md5(
                decision.task_description.encode()
            ).hexdigest()

        cursor = self._db.execute(
            """INSERT INTO routing_decisions
               (decision_id, task_description, task_hash, selected_agent,
                routing_strategy, status, confidence_score, execution_time_ms,
                context_json, user_id, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                decision.decision_id,
                decision.task_description,
                decision.task_hash,
                decision.selected_agent,
                decision.routing_strategy.value,
                decision.status.value,
                decision.confidence_score,
                decision.execution_time_ms,
                decision.context_json,
                decision.user_id,
                decision.session_id,
            ),
        )
        decision_id = cursor.lastrowid

        if candidates:
            for c in candidates:
                self._db.execute(
                    """INSERT INTO candidate_scores
                       (decision_id, agent_name, score, rank, features_json)
                       VALUES (?, ?, ?, ?, ?)""",
                    (decision_id, c.agent_name, c.score, c.rank, c.features_json),
                )

        self._db.commit()
        return decision_id

    def find_decisions(
        self,
        agent_name: str | None = None,
        strategy: RoutingStrategy | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RoutingDecision]:
        conditions = ["1=1"]
        params: list = []
        if agent_name:
            conditions.append("selected_agent=?")
            params.append(agent_name)
        if strategy:
            conditions.append("routing_strategy=?")
            params.append(strategy.value)

        rows = self._db.execute(
            f"SELECT * FROM routing_decisions WHERE {' AND '.join(conditions)} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()

        return [self._row_to_decision(r) for r in rows]

    def get_analytics(self) -> dict[str, Any]:
        total = self._db.execute(
            "SELECT COUNT(*) as cnt FROM routing_decisions"
        ).fetchone()["cnt"]

        success = self._db.execute(
            "SELECT COUNT(*) as cnt FROM routing_decisions WHERE status='success'"
        ).fetchone()["cnt"]

        by_strategy = {}
        rows = self._db.execute(
            "SELECT routing_strategy, COUNT(*) as cnt FROM routing_decisions GROUP BY routing_strategy"
        ).fetchall()
        for r in rows:
            by_strategy[r["routing_strategy"]] = r["cnt"]

        return {
            "total_decisions": total,
            "success_count": success,
            "success_rate": success / total if total > 0 else 0,
            "by_strategy": by_strategy,
        }

    def get_agent_performance(self, agent_name: str) -> dict[str, Any]:
        row = self._db.execute(
            "SELECT * FROM agent_performance WHERE agent_name=?",
            (agent_name,),
        ).fetchone()
        if row:
            return dict(row)
        return {"agent_name": agent_name, "total_tasks": 0}

    def record_feedback(self, decision_id: int, feedback: UserFeedback) -> bool:
        fb_type = feedback.feedback_type
        if hasattr(fb_type, "value"):
            fb_type = fb_type.value
        self._db.execute(
            """INSERT INTO user_feedback
               (decision_id, feedback_type, corrected_agent, feedback_text, rating)
               VALUES (?, ?, ?, ?, ?)""",
            (
                decision_id,
                fb_type,
                feedback.corrected_agent,
                feedback.feedback_text,
                feedback.rating,
            ),
        )
        self._db.commit()
        return True

    def get_ml_training_data(self, limit: int = 1000) -> tuple[list[str], list[str]]:
        rows = self._db.execute(
            "SELECT task_description, selected_agent FROM routing_decisions "
            f"WHERE selected_agent IS NOT NULL ORDER BY created_at DESC LIMIT {limit}"
        ).fetchall()
        texts = [r["task_description"] for r in rows]
        labels = [r["selected_agent"] for r in rows]
        return texts, labels

    # ---- 语义路由器：关键词特征 ----

    def get_keyword_features(self) -> list[dict[str, Any]]:
        """获取所有关键词特征权重。"""
        rows = self._db.execute(
            "SELECT keyword, agent_name, occurrence_count, success_rate, last_used "
            "FROM keyword_features ORDER BY occurrence_count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_keyword_feature(self, keyword: str, agent_name: str, success: bool) -> None:
        """更新关键词特征（成功/失败计数）。"""
        existing = self._db.execute(
            "SELECT occurrence_count, success_rate FROM keyword_features "
            "WHERE keyword=? AND agent_name=?", (keyword, agent_name)
        ).fetchone()

        if existing:
            cnt = existing["occurrence_count"] + 1
            old_rate = existing["success_rate"] or 0.5
            new_rate = ((old_rate * (cnt - 1)) + (1.0 if success else 0.0)) / cnt
            self._db.execute(
                "UPDATE keyword_features SET occurrence_count=?, success_rate=?, "
                "last_used=CURRENT_TIMESTAMP WHERE keyword=? AND agent_name=?",
                (cnt, new_rate, keyword, agent_name),
            )
        else:
            self._db.execute(
                "INSERT INTO keyword_features (keyword, agent_name, occurrence_count, success_rate, last_used) "
                "VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)",
                (keyword, agent_name, 1.0 if success else 0.0),
            )
        self._db.commit()

    # ---- 自适应路由器：策略性能 ----

    def get_strategy_performance(self) -> list[dict[str, Any]]:
        """获取所有策略的性能指标。"""
        rows = self._db.execute(
            "SELECT * FROM strategy_performance ORDER BY total_decisions DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_strategy_performance(
        self,
        strategy_name: str,
        success: bool,
        confidence: float = 0.0,
        execution_time_ms: float = 0.0,
        feedback_correct: bool | None = None,
    ) -> None:
        """更新策略性能指标。"""
        existing = self._db.execute(
            "SELECT * FROM strategy_performance WHERE strategy_name=?",
            (strategy_name,),
        ).fetchone()

        if existing:
            td = existing["total_decisions"] + 1
            sr = ((existing["success_rate"] or 0) * existing["total_decisions"] + (1.0 if success else 0.0)) / td
            ac = ((existing["avg_confidence"] or 0) * existing["total_decisions"] + confidence) / td
            at = ((existing["avg_execution_time_ms"] or 0) * existing["total_decisions"] + execution_time_ms) / td
            fcr = existing["feedback_correct_rate"]
            if feedback_correct is not None:
                fcr = ((fcr or 0) * max(existing["total_decisions"] - 1, 1) + (1.0 if feedback_correct else 0.0)) / td

            self._db.execute(
                "UPDATE strategy_performance SET total_decisions=?, success_rate=?, "
                "avg_confidence=?, avg_execution_time_ms=?, feedback_correct_rate=? "
                "WHERE strategy_name=?",
                (td, sr, ac, at, fcr, strategy_name),
            )
        else:
            self._db.execute(
                "INSERT INTO strategy_performance (strategy_name, total_decisions, success_rate, "
                "avg_confidence, avg_execution_time_ms, feedback_correct_rate, weight) "
                "VALUES (?, 1, ?, ?, ?, ?, 1.0)",
                (strategy_name, 1.0 if success else 0.0, confidence, execution_time_ms,
                 1.0 if (feedback_correct if feedback_correct is not None else success) else 0.0),
            )
        self._db.commit()

    # ---- 上下文路由器：智能体画像 ----

    def get_agent_context_profile(self, agent_name: str) -> dict[str, Any]:
        """获取智能体上下文偏好画像（从 agent_performance 聚合）。"""
        row = self._db.execute(
            "SELECT * FROM agent_performance WHERE agent_name=?", (agent_name,)
        ).fetchone()
        if row:
            return dict(row)
        return {"agent_name": agent_name, "total_tasks": 0, "success_count": 0}

    def update_agent_context_outcome(self, agent_name: str, success: bool) -> None:
        """更新智能体上下文路由结果。"""
        existing = self._db.execute(
            "SELECT * FROM agent_performance WHERE agent_name=?", (agent_name,)
        ).fetchone()
        if existing:
            td = existing["total_tasks"] + 1
            sc = existing["success_count"] + (1 if success else 0)
            self._db.execute(
                "UPDATE agent_performance SET total_tasks=?, success_count=?, "
                "last_updated=CURRENT_TIMESTAMP WHERE agent_name=?",
                (td, sc, agent_name),
            )
        else:
            self._db.execute(
                "INSERT INTO agent_performance (agent_name, total_tasks, success_count, last_updated) "
                "VALUES (?, 1, ?, CURRENT_TIMESTAMP)",
                (agent_name, 1 if success else 0),
            )
        self._db.commit()

    def _row_to_decision(self, row) -> RoutingDecision:
        return RoutingDecision(
            id=row["id"],
            decision_id=row["decision_id"],
            task_description=row["task_description"],
            task_hash=row["task_hash"],
            selected_agent=row["selected_agent"],
            routing_strategy=RoutingStrategy(row["routing_strategy"]),
            status=RoutingStatus(row["status"]),
            confidence_score=row["confidence_score"],
            execution_time_ms=row["execution_time_ms"],
            context_json=row["context_json"],
            created_at=row["created_at"],
            user_id=row["user_id"],
            session_id=row["session_id"],
        )
