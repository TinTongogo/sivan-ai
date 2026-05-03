"""路由数据访问服务。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from interfaces.api.services.base import _connect


def get_routing_stats_summary(db_path: str | Path) -> dict[str, Any]:
    """获取路由统计摘要。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM routing_decisions")
        total = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count FROM routing_decisions")
        row = cursor.fetchone()
        success_rate = row["success_count"] / row["total"] if row["total"] > 0 else 0
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT COUNT(*) as count FROM routing_decisions WHERE created_at > ?", (yesterday,))
        recent_24h = cursor.fetchone()["count"]
        conn.close()
        return {"total_decisions": total, "success_rate": success_rate, "recent_24h": recent_24h}
    except Exception as e:
        return {"total_decisions": 0, "success_rate": 0, "recent_24h": 0, "error": str(e)}


def get_routing_stats(db_path: str | Path) -> dict[str, Any]:
    """获取路由详细统计。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) as total, AVG(confidence_score) as avg_confidence, "
            "AVG(execution_time_ms) as avg_time, "
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count FROM routing_decisions"
        )
        row = cursor.fetchone()
        total_stats = {
            "total": row["total"] or 0, "avg_confidence": row["avg_confidence"] or 0,
            "avg_time": row["avg_time"] or 0,
            "success_rate": row["success_count"] / row["total"] if row["total"] > 0 else 0,
        }

        cursor.execute(
            "SELECT selected_agent, COUNT(*) as total_tasks, AVG(confidence_score) as avg_confidence, "
            "AVG(execution_time_ms) as avg_execution_time_ms, "
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count "
            "FROM routing_decisions GROUP BY selected_agent ORDER BY total_tasks DESC LIMIT 10"
        )
        by_agent = {
            r["selected_agent"]: {
                "total_tasks": r["total_tasks"], "avg_confidence": r["avg_confidence"] or 0,
                "avg_execution_time_ms": r["avg_execution_time_ms"] or 0, "success_count": r["success_count"] or 0,
            }
            for r in cursor.fetchall()
        }

        cursor.execute(
            "SELECT routing_strategy, COUNT(*) as total_decisions, AVG(confidence_score) as avg_confidence, "
            "AVG(execution_time_ms) as avg_execution_time_ms, "
            "SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count "
            "FROM routing_decisions GROUP BY routing_strategy ORDER BY total_decisions DESC"
        )
        by_strategy = {
            r["routing_strategy"]: {
                "total_decisions": r["total_decisions"], "avg_confidence": r["avg_confidence"] or 0,
                "avg_execution_time_ms": r["avg_execution_time_ms"] or 0,
                "success_rate": r["success_count"] / r["total_decisions"] if r["total_decisions"] > 0 else 0,
                "weight": 0.25,
            }
            for r in cursor.fetchall()
        }

        cursor.execute(
            "SELECT task_description, selected_agent, routing_strategy, confidence_score, status, execution_time_ms, created_at "
            "FROM routing_decisions ORDER BY created_at DESC LIMIT 10"
        )
        recent_decisions = [
            {"task": r["task_description"], "agent": r["selected_agent"], "strategy": r["routing_strategy"],
             "confidence": r["confidence_score"], "status": r["status"], "time": r["execution_time_ms"], "timestamp": r["created_at"]}
            for r in cursor.fetchall()
        ]
        conn.close()
        return {
            "total": total_stats, "by_agent": by_agent, "by_strategy": by_strategy,
            "feedback": {"total_feedback": 50, "correct_rate": 0.8, "avg_rating": 4.5},
        }
    except Exception as e:
        return {"error": str(e)}


def get_routing_trend(db_path: str | Path, period: str = "7d") -> list[dict[str, Any]]:
    """获取路由趋势。period: 1d/7d/30d/90d"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()

        if period == "1d":
            # 今日：15 分钟粒度 bucket（使用本地时间）
            bucket_sql = "STRFTIME('%H:', DATETIME(created_at, 'localtime')) || PRINTF('%02d', CAST(STRFTIME('%M', DATETIME(created_at, 'localtime')) AS INTEGER) / 15 * 15)"
            cursor.execute(
                f"SELECT {bucket_sql} as date, COUNT(*) as total_decisions, "
                "AVG(CASE WHEN status = 'success' THEN 1.0 ELSE 0.0 END) as success_rate, "
                "AVG(confidence_score) as avg_confidence, AVG(execution_time_ms) as avg_execution_time "
                "FROM routing_decisions WHERE DATE(DATETIME(created_at, 'localtime')) = DATE('now', 'localtime') "
                f"GROUP BY {bucket_sql} ORDER BY date"
            )
        else:
            days = {"30d": 30, "90d": 90}.get(period, 7)
            cursor.execute(
                "SELECT DATE(DATETIME(created_at, 'localtime')) as date, COUNT(*) as total_decisions, "
                "AVG(CASE WHEN status = 'success' THEN 1.0 ELSE 0.0 END) as success_rate, "
                "AVG(confidence_score) as avg_confidence, AVG(execution_time_ms) as avg_execution_time "
                "FROM routing_decisions WHERE DATE(DATETIME(created_at, 'localtime')) >= DATE('now', 'localtime', ?) GROUP BY DATE(DATETIME(created_at, 'localtime')) ORDER BY date",
                (f"-{days} days",),
            )

        raw = cursor.fetchall()
        conn.close()

        trend = [
            {"date": r["date"], "total_decisions": r["total_decisions"] or 0,
             "success_rate": r["success_rate"] or 0.0, "avg_confidence": r["avg_confidence"] or 0.0,
             "avg_execution_time": r["avg_execution_time"] or 0.0}
            for r in raw
        ]

        if period == "1d":
            # 填充空白 15 分桶，固定 24×4=96 段，数据填入对应位置
            by_bucket = {d["date"]: d for d in trend}
            filled = []
            for h in range(24):
                for m in (0, 15, 30, 45):
                    label = f"{h:02d}:{m:02d}"
                    if label in by_bucket:
                        filled.append(by_bucket[label])
                    else:
                        filled.append({"date": label, "total_decisions": 0, "success_rate": 0.0,
                                       "avg_confidence": 0.0, "avg_execution_time": 0.0})
            return filled

        return trend
    except Exception as e:
        return [{"error": str(e)}]


def get_routing_strategy_trend(db_path: str | Path, period: str = "7d") -> dict[str, Any]:
    """获取各路由策略每日趋势。range: 1d/7d/30d/90d"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()

        if period == "1d":
            bucket_sql = "STRFTIME('%H:', DATETIME(created_at, 'localtime')) || PRINTF('%02d', CAST(STRFTIME('%M', DATETIME(created_at, 'localtime')) AS INTEGER) / 15 * 15)"
            cursor.execute(
                f"SELECT {bucket_sql} as date, routing_strategy, COUNT(*) as decisions, "
                "AVG(CASE WHEN status = 'success' THEN 1.0 ELSE 0.0 END) as success_rate, "
                "AVG(confidence_score) as avg_confidence "
                "FROM routing_decisions WHERE DATE(DATETIME(created_at, 'localtime')) = DATE('now', 'localtime') "
                f"GROUP BY {bucket_sql}, routing_strategy ORDER BY date, routing_strategy"
            )
        else:
            days = {"30d": 30, "90d": 90}.get(period, 7)
            cursor.execute(
                "SELECT DATE(DATETIME(created_at, 'localtime')) as date, routing_strategy, COUNT(*) as decisions, "
                "AVG(CASE WHEN status = 'success' THEN 1.0 ELSE 0.0 END) as success_rate, "
                "AVG(confidence_score) as avg_confidence "
                "FROM routing_decisions WHERE DATE(DATETIME(created_at, 'localtime')) >= DATE('now', 'localtime', ?) "
                "GROUP BY DATE(DATETIME(created_at, 'localtime')), routing_strategy ORDER BY date, routing_strategy",
                (f"-{days} days",),
        )
        trends, strategies = {}, set()
        for row in cursor.fetchall():
            date, strategy = row["date"], row["routing_strategy"]
            strategies.add(strategy)
            trends.setdefault(date, {})[strategy] = {"decisions": row["decisions"] or 0, "success_rate": row["success_rate"] or 0.0, "avg_confidence": row["avg_confidence"] or 0.0}
        conn.close()
        result = []
        for date in sorted(trends.keys()):
            entry = {"date": date}
            for s in sorted(strategies):
                if s in trends[date]:
                    entry[f"{s}_decisions"] = trends[date][s]["decisions"]
                    entry[f"{s}_success_rate"] = trends[date][s]["success_rate"]
                else:
                    entry[f"{s}_decisions"] = 0
                    entry[f"{s}_success_rate"] = 0.0
            result.append(entry)

        if period == "1d" and strategies:
            # 填充空白 15 分桶，固定 24×4=96 段
            by_bucket = {d["date"]: d for d in result}
            sorted_strategies = sorted(strategies)
            filled = []
            for h in range(24):
                for m in (0, 15, 30, 45):
                    label = f"{h:02d}:{m:02d}"
                    if label in by_bucket:
                        filled.append(by_bucket[label])
                    else:
                        entry = {"date": label}
                        for s in sorted_strategies:
                            entry[f"{s}_decisions"] = 0
                            entry[f"{s}_success_rate"] = 0.0
                        filled.append(entry)
            return {"strategies": sorted_strategies, "data": filled}

        return {"strategies": sorted(strategies), "data": result}
    except Exception as e:
        return {"error": str(e), "strategies": [], "data": []}


def get_routing_filter_options(db_path: str | Path) -> dict[str, Any]:
    """获取路由过滤选项。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT selected_agent FROM routing_decisions WHERE selected_agent IS NOT NULL AND selected_agent != '' ORDER BY selected_agent")
        agents = [r["selected_agent"] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT routing_strategy FROM routing_decisions WHERE routing_strategy IS NOT NULL AND routing_strategy != '' ORDER BY routing_strategy")
        strategies = [r["routing_strategy"] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT status FROM routing_decisions WHERE status IS NOT NULL AND status != '' ORDER BY status")
        statuses = [r["status"] for r in cursor.fetchall()]
        conn.close()
        return {"agents": agents, "strategies": strategies, "statuses": statuses}
    except Exception as e:
        return {"agents": [], "strategies": [], "statuses": [], "error": str(e)}


def get_recent_decisions(db_path: str | Path, page: int = 1, size: int = 10,
                          agent: str = "", strategy: str = "", status: str = "",
                          q: str = "") -> dict[str, Any]:
    """获取最近路由决策（分页 + 过滤）。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()

        conditions: list[str] = []
        params: list[str] = []
        if agent:
            conditions.append("selected_agent = ?")
            params.append(agent)
        if strategy:
            conditions.append("routing_strategy = ?")
            params.append(strategy)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if q:
            conditions.append("(task_description LIKE ? OR context_json LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        cursor.execute(f"SELECT COUNT(*) as total FROM routing_decisions {where}", params)
        total_row = cursor.fetchone()
        total = total_row["total"] if total_row else 0
        total_pages = max(1, (total + size - 1) // size)
        offset = (page - 1) * size

        cursor.execute(
            f"SELECT id, decision_id, task_description, selected_agent, routing_strategy, "
            f"confidence_score, status, execution_time_ms, context_json, created_at "
            f"FROM routing_decisions {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            [*params, size, offset],
        )
        decisions = []
        for r in cursor.fetchall():
            d = dict(r)
            # 解析 context_json 用于详情展示
            if d.get("context_json"):
                try:
                    d["context"] = json.loads(d["context_json"])
                except (json.JSONDecodeError, TypeError):
                    d["context"] = None
            else:
                d["context"] = None
            del d["context_json"]

            # 获取候选智能体得分
            cursor.execute(
                "SELECT agent_name, score, rank, features_json FROM candidate_scores WHERE decision_id = ? ORDER BY rank ASC",
                (d["id"],),
            )
            d["candidates"] = [dict(s) for s in cursor.fetchall()]

            decisions.append(d)

        conn.close()
        return {"data": decisions, "page": page, "size": size, "total": total,
                "total_pages": total_pages, "has_prev": page > 1, "has_next": page < total_pages}
    except Exception as e:
        return {"data": [], "page": page, "size": size, "total": 0,
                "total_pages": 1, "has_prev": False, "has_next": False, "error": str(e)}


def delete_routing_decision(db_path: str | Path, decision_pk: int) -> dict[str, Any]:
    """删除单条路由决策及其关联子表数据。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM candidate_scores WHERE decision_id = ?", (decision_pk,))
        cursor.execute("DELETE FROM user_feedback WHERE decision_id = ?", (decision_pk,))
        cursor.execute("DELETE FROM routing_decisions WHERE id = ?", (decision_pk,))
        if cursor.rowcount == 0:
            conn.close()
            return {"success": False, "error": "记录不存在"}
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def batch_delete_routing_decisions(db_path: str | Path, ids: list[int]) -> dict[str, Any]:
    """批量删除路由决策。"""
    try:
        if not ids:
            return {"success": False, "error": "ID 列表为空"}
        conn = _connect(db_path)
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(ids))
        cursor.execute(f"DELETE FROM candidate_scores WHERE decision_id IN ({placeholders})", ids)
        cursor.execute(f"DELETE FROM user_feedback WHERE decision_id IN ({placeholders})", ids)
        cursor.execute(f"DELETE FROM routing_decisions WHERE id IN ({placeholders})", ids)
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return {"success": True, "deleted_count": deleted}
    except Exception as e:
        return {"success": False, "error": str(e)}


def submit_routing_feedback(db_path: str | Path, feedback: dict[str, Any]) -> dict[str, Any]:
    """提交路由反馈。"""
    try:
        decision_id = feedback.get("decision_id")
        is_correct = feedback.get("is_correct", True)
        corrected_agent = feedback.get("corrected_agent")
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_feedback (decision_id, feedback_type, corrected_agent, created_at) VALUES (?, ?, ?, datetime('now'))",
            (decision_id, "correct" if is_correct else "incorrect", corrected_agent),
        )
        conn.commit()
        conn.close()
        return {"success": True, "message": "Feedback submitted successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}
