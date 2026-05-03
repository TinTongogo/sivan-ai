"""Token 使用统计仓库 SQLite 实现。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from infrastructure.persistence.connection import SQLiteConnectionManager


class TokenUsageRepository:
    """基于 SQLite 的 Token 使用统计仓库。"""

    def __init__(self, connection_manager: SQLiteConnectionManager) -> None:
        self._db = connection_manager
        self._init_tables()

    MODEL_PRICES: dict[str, dict[str, float]] = {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "deepseek-chat": {"input": 0.5, "output": 2.0},
    }

    def _init_tables(self) -> None:
        pass  # schema 由 Alembic 管理

    def record_usage(
        self,
        agent_name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        task_description: str = "",
    ) -> int:
        prices = self.MODEL_PRICES.get(model, {"input": 1.0, "output": 2.0})
        cost = (input_tokens / 1_000_000 * prices["input"]) + (
            output_tokens / 1_000_000 * prices["output"]
        )
        total = input_tokens + output_tokens

        cursor = self._db.execute(
            """INSERT INTO token_usage
               (agent_name, model, input_tokens, output_tokens, total_tokens, cost_usd, task_description)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent_name, model, input_tokens, output_tokens, total, cost, task_description),
        )
        self._db.commit()
        return cursor.lastrowid

    def get_stats(
        self,
        period: str = "daily",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        row = self._db.execute(
            """SELECT
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(cost_usd), 0) as total_cost
               FROM token_usage
               WHERE DATE(DATETIME(timestamp, 'localtime')) >= ? AND DATE(DATETIME(timestamp, 'localtime')) <= ?""",
            (start_date, end_date),
        ).fetchone()

        agent_rows = self._db.execute(
            """SELECT agent_name,
                      SUM(input_tokens) as input_tokens,
                      SUM(output_tokens) as output_tokens,
                      SUM(total_tokens) as total_tokens,
                      SUM(cost_usd) as cost_usd
               FROM token_usage
               WHERE DATE(DATETIME(timestamp, 'localtime')) >= ? AND DATE(DATETIME(timestamp, 'localtime')) <= ?
               GROUP BY agent_name""",
            (start_date, end_date),
        ).fetchall()

        agent_breakdown = {}
        for r in agent_rows:
            agent_breakdown[r["agent_name"]] = dict(r)

        return {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "total_input_tokens": row["total_input"] or 0,
            "total_output_tokens": row["total_output"] or 0,
            "total_tokens": row["total_tokens"] or 0,
            "total_cost_usd": row["total_cost"] or 0.0,
            "agent_breakdown": agent_breakdown,
        }

    def get_daily_budget(self, date: str | None = None) -> dict[str, Any]:
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        row = self._db.execute(
            "SELECT * FROM daily_budgets WHERE date=?",
            (date,),
        ).fetchone()

        budget_row = self._db.execute(
            "SELECT * FROM token_budget ORDER BY id DESC LIMIT 1"
        ).fetchone()

        spent = self._db.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) as spent FROM token_usage WHERE DATE(DATETIME(timestamp, 'localtime'))=?",
            (date,),
        ).fetchone()

        return {
            "date": date,
            "daily_budget": budget_row["daily_budget_usd"] if budget_row else 0.0,
            "spent_today": spent["spent"] if spent else 0.0,
            "remaining": (budget_row["daily_budget_usd"] if budget_row else 0.0) - (spent["spent"] if spent else 0.0),
            "has_budget": bool(budget_row),
        }
