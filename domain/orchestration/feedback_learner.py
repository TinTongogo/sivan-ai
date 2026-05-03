"""编排拓扑反馈学习器。

记录任务特征→拓扑映射的用户满意度，驱动编排风格演化。
当某类任务有明确偏好的拓扑时，反馈学习器优先推荐该拓扑。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("sivan.topology.feedback")


class TopologyFeedbackLearner:
    """编排拓扑反馈学习器。

    存储用户对每次编排拓扑的满意度评分，
    支持查询某类任务最受认可的拓扑。
    """

    def __init__(self, db_conn) -> None:
        """Args:
            db_conn: SQLiteConnectionManager 实例或具有 execute/commit 方法的对象
        """
        self._db = db_conn

    def record_outcome(
        self,
        task_signature: str,
        topology: dict[str, Any],
        satisfaction: float,
        execution_id: str = "",
    ) -> int:
        """记录一次编排结果的满意度评分。

        Args:
            task_signature: 归一化任务特征
            topology: 使用的编排拓扑 dict
            satisfaction: 满意度评分 (0.0 ~ 1.0)
            execution_id: 执行记录 ID（可选）

        Returns:
            int: 记录 ID
        """
        import json
        topology_str = json.dumps(topology, ensure_ascii=False)
        self._db.execute(
            """INSERT INTO topology_feedback
               (task_signature, topology, satisfaction, execution_id)
               VALUES (?, ?, ?, ?)""",
            (task_signature, topology_str, satisfaction, execution_id),
        )
        self._db.commit()
        row = self._db.execute("SELECT last_insert_rowid() as rid").fetchone()
        rid = row["rid"] if row else 0
        logger.info("拓扑反馈记录: id=%s, sig=%s, sat=%.2f", rid, task_signature[:30], satisfaction)
        return rid

    def get_preferred_topology(self, task_signature: str) -> dict[str, Any] | None:
        """返回该任务特征满意度最高的拓扑。

        Args:
            task_signature: 归一化任务特征

        Returns:
            dict | None: 满意度最高的拓扑 dict，若无记录则返回 None
        """
        rows = self._db.execute(
            """SELECT topology, satisfaction FROM topology_feedback
               WHERE task_signature = ?
               ORDER BY satisfaction DESC LIMIT 1""",
            (task_signature,),
        ).fetchall()
        if not rows:
            return None
        import json
        try:
            topology = json.loads(rows[0]["topology"])
            topology["from_feedback"] = True
            topology["feedback_satisfaction"] = rows[0]["satisfaction"]
            return topology
        except (json.JSONDecodeError, KeyError, IndexError):
            return None

    def get_stats(self) -> dict[str, Any]:
        """获取反馈统计。"""
        total = self._db.execute(
            "SELECT COUNT(*) as cnt FROM topology_feedback"
        ).fetchone()
        avg_sat = self._db.execute(
            "SELECT AVG(satisfaction) as avg_sat FROM topology_feedback"
        ).fetchone()
        unique_sigs = self._db.execute(
            "SELECT COUNT(DISTINCT task_signature) as cnt FROM topology_feedback"
        ).fetchone()
        return {
            "total_records": total["cnt"] if total else 0,
            "avg_satisfaction": round(avg_sat["avg_sat"], 4) if avg_sat and avg_sat["avg_sat"] else 0.0,
            "unique_signatures": unique_sigs["cnt"] if unique_sigs else 0,
        }

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """列出最近的反馈记录。"""
        import json
        rows = self._db.execute(
            """SELECT id, task_signature, topology, satisfaction, execution_id, created_at
               FROM topology_feedback ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["topology"] = json.loads(item["topology"])
            except (json.JSONDecodeError, TypeError):
                pass
            result.append(item)
        return result
