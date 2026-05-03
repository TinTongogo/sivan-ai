"""Token 统计与预算数据访问服务。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from interfaces.api.services.base import _connect


def get_token_stats_summary(db_path: str | Path) -> dict[str, Any]:
    """获取Token统计摘要。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_tokens) as total FROM token_usage")
        total_tokens = cursor.fetchone()["total"] or 0
        cursor.execute("SELECT SUM(cost_usd) as total FROM token_usage")
        total_cost = cursor.fetchone()["total"] or 0.0
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            "SELECT SUM(total_tokens) as total, SUM(cost_usd) as cost FROM token_usage WHERE DATE(timestamp) = ?",
            (today,),
        )
        row = cursor.fetchone()
        conn.close()
        return {
            "total_tokens": total_tokens, "total_cost": total_cost,
            "today_tokens": row["total"] or 0, "today_cost": row["cost"] or 0.0,
        }
    except Exception as e:
        return {"total_tokens": 0, "total_cost": 0.0, "today_tokens": 0, "today_cost": 0.0, "error": str(e)}


def get_token_stats(db_path: str | Path) -> dict[str, Any]:
    """获取Token详细统计。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT SUM(input_tokens) as total_input, SUM(output_tokens) as total_output, "
            "SUM(total_tokens) as total_tokens, SUM(cost_usd) as total_cost, COUNT(*) as total_requests FROM token_usage"
        )
        row = cursor.fetchone()
        total_stats = {
            "total_input": row["total_input"] or 0, "total_output": row["total_output"] or 0,
            "total_tokens": row["total_tokens"] or 0, "total_cost": row["total_cost"] or 0.0,
            "total_requests": row["total_requests"] or 0,
        }

        cursor.execute(
            "SELECT agent_name, SUM(total_tokens) as total_tokens, SUM(cost_usd) as total_cost, COUNT(*) as total_requests "
            "FROM token_usage GROUP BY agent_name ORDER BY total_tokens DESC LIMIT 10"
        )
        by_agent = {r["agent_name"]: {"total_tokens": r["total_tokens"], "total_cost": r["total_cost"], "total_requests": r["total_requests"]} for r in cursor.fetchall()}

        cursor.execute(
            "SELECT model, SUM(total_tokens) as total_tokens, SUM(cost_usd) as total_cost, COUNT(*) as total_requests "
            "FROM token_usage GROUP BY model ORDER BY total_tokens DESC LIMIT 10"
        )
        by_model = {r["model"]: {"total_tokens": r["total_tokens"], "total_cost": r["total_cost"], "total_requests": r["total_requests"]} for r in cursor.fetchall()}

        cursor.execute(
            "SELECT agent_name, model, total_tokens, cost_usd, timestamp FROM token_usage ORDER BY timestamp DESC LIMIT 10"
        )
        recent_usage = [
            {"agent_name": r["agent_name"], "model": r["model"], "tokens": r["total_tokens"], "cost": r["cost_usd"], "timestamp": r["timestamp"]}
            for r in cursor.fetchall()
        ]

        cursor.execute("SELECT daily_budget, monthly_budget, alert_email FROM token_budget WHERE id = 1")
        budget_row = cursor.fetchone()
        budget = {
            "daily_budget": budget_row["daily_budget"] if budget_row else 10.0,
            "monthly_budget": budget_row["monthly_budget"] if budget_row else 300.0,
            "alert_email": budget_row["alert_email"] if budget_row else "",
        }
        conn.close()
        return {"total": total_stats, "by_agent": by_agent, "by_model": by_model, "recent": recent_usage, "budget": budget}
    except Exception as e:
        return {"error": str(e)}


def get_token_daily_trend(db_path: str | Path, period: str = "7d") -> list[dict[str, Any]]:
    """获取Token每日趋势。period: 1d/7d/30d/90d"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()

        if period == "1d":
            # 今日：15 分钟粒度 bucket（使用本地时间）
            bucket_sql = "STRFTIME('%H:', DATETIME(timestamp, 'localtime')) || PRINTF('%02d', CAST(STRFTIME('%M', DATETIME(timestamp, 'localtime')) AS INTEGER) / 15 * 15)"
            cursor.execute(
                f"SELECT {bucket_sql} as date, SUM(total_tokens) as total_tokens, "
                "SUM(cost_usd) as total_cost, COUNT(*) as total_requests "
                "FROM token_usage WHERE DATE(DATETIME(timestamp, 'localtime')) = DATE('now', 'localtime') "
                f"GROUP BY {bucket_sql} ORDER BY date"
            )
        else:
            days = {"30d": 30, "90d": 90}.get(period, 7)
            cursor.execute(
                "SELECT DATE(DATETIME(timestamp, 'localtime')) as date, SUM(total_tokens) as total_tokens, SUM(cost_usd) as total_cost, COUNT(*) as total_requests "
                "FROM token_usage WHERE DATE(DATETIME(timestamp, 'localtime')) >= DATE('now', 'localtime', ?) GROUP BY DATE(DATETIME(timestamp, 'localtime')) ORDER BY date",
                (f"-{days} days",),
            )

        raw = cursor.fetchall()
        conn.close()

        trend = [{"date": r["date"], "total_tokens": r["total_tokens"] or 0, "total_cost": r["total_cost"] or 0.0, "total_requests": r["total_requests"] or 0} for r in raw]

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
                        filled.append({"date": label, "total_tokens": 0, "total_cost": 0.0, "total_requests": 0})
            return filled

        return trend
    except Exception as e:
        return [{"error": str(e)}]


def update_token_budget(db_path: str | Path, budget: dict[str, Any]) -> dict[str, Any]:
    """更新Token预算。"""
    try:
        daily = budget.get("daily_budget", 10.0)
        monthly = budget.get("monthly_budget", 300.0)
        email = budget.get("alert_email", "")
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO token_budget (id, daily_budget, monthly_budget, alert_email) VALUES (1, ?, ?, ?)", (daily, monthly, email))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Budget updated successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_token_usage(db_path: str | Path, period: str = "7d") -> dict[str, Any]:
    """删除指定时间段内的 Token 使用数据，同时清理超过 90 天的旧数据。

    period: 1d/7d/30d/90d
    """
    days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}.get(period, 7)
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        # 删除选定时间段内 + 超过 90 天的数据
        cursor.execute(
            "DELETE FROM token_usage "
            "WHERE DATE(DATETIME(timestamp, 'localtime')) >= DATE('now', 'localtime', ?) "
            "   OR DATE(DATETIME(timestamp, 'localtime')) < DATE('now', 'localtime', '-90 days')",
            (f"-{days} days",),
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return {"success": True, "deleted": deleted}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_budget_alerts(db_path: str | Path) -> list[dict[str, Any]]:
    """检查预算使用情况，超阈值时返回告警。"""
    alerts = []
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT daily_budget, monthly_budget, alert_email FROM token_budget WHERE id = 1")
        budget_row = cursor.fetchone()
        if not budget_row or not budget_row["alert_email"]:
            conn.close()
            return []
        daily_budget, _, alert_email = budget_row["daily_budget"], budget_row["monthly_budget"], budget_row["alert_email"]

        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT COALESCE(SUM(cost_usd), 0) as today_spent FROM token_usage WHERE DATE(DATETIME(timestamp, 'localtime')) = DATE('now', 'localtime')")
        today_spent = cursor.fetchone()["today_spent"]
        conn.close()

        daily_pct = (today_spent / daily_budget * 100) if daily_budget > 0 else 0

        conn2 = _connect(db_path)
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT alert_sent FROM daily_budgets WHERE date = ?", (today,))
        alert_row = cursor2.fetchone()
        alert_sent = alert_row and alert_row["alert_sent"]
        conn2.close()

        if daily_pct >= 100 and not alert_sent:
            alerts.append({"type": "budget_exceeded", "severity": "critical", "message": f"今日预算已超限！已使用 ${today_spent:.4f} / ${daily_budget:.4f}", "budget_usd": daily_budget, "spent_usd": round(today_spent, 4), "remaining_usd": 0})
            conn3 = _connect(db_path)
            c3 = conn3.cursor()
            c3.execute("INSERT OR REPLACE INTO daily_budgets (date, budget_usd, spent_usd, alert_sent) VALUES (?, ?, ?, 1)", (today, daily_budget, round(today_spent, 4)))
            conn3.commit()
            conn3.close()
        elif daily_pct >= 80 and daily_pct < 100 and not alert_sent:
            alerts.append({"type": "budget_warning", "severity": "warning", "message": f"今日预算已使用 {daily_pct:.1f}% (${today_spent:.4f} / ${daily_budget:.4f})", "budget_usd": daily_budget, "spent_usd": round(today_spent, 4), "remaining_usd": round(daily_budget - today_spent, 4)})
        return alerts
    except Exception:
        return []
