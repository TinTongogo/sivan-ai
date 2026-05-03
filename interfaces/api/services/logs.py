"""执行日志查询服务。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def _get_conn(db_path: str | Path) -> sqlite3.Connection:
    from interfaces.api.services.base import get_conn as _shared_conn
    return _shared_conn(db_path)


def get_logs(
    db_path: str | Path,
    *,
    limit: int = 50,
    offset: int = 0,
    level: str = "",
    source: str = "",
    action: str = "",
    trace_id: str = "",
    q: str = "",
) -> dict[str, Any]:
    """查询 execution_logs，支持多维过滤 + 分页。"""
    try:
        conn = _get_conn(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where = []
        params: list[Any] = []

        if level:
            placeholders = [l.strip() for l in level.split(",") if l.strip()]
            if placeholders:
                where.append(f"level IN ({','.join(['?'] * len(placeholders))})")
                params.extend(placeholders)
        if source:
            where.append("source = ?")
            params.append(source)
        if action:
            where.append("action = ?")
            params.append(action)
        if trace_id:
            where.append("trace_id = ?")
            params.append(trace_id)
        if q:
            where.append("(message LIKE ? OR metadata LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        # Total count
        cursor.execute(f"SELECT COUNT(*) as cnt FROM execution_logs {where_clause}", params)
        total = cursor.fetchone()["cnt"]

        # Data
        cursor.execute(
            f"SELECT * FROM execution_logs {where_clause} ORDER BY log_id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        logs = [dict(row) for row in cursor.fetchall()]

        # Filter options
        cursor.execute("SELECT DISTINCT source FROM execution_logs ORDER BY source")
        sources = [row["source"] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT level FROM execution_logs ORDER BY level")
        levels = [row["level"] for row in cursor.fetchall()]

        conn.close()
        return {"logs": logs, "total": total, "limit": limit, "offset": offset, "sources": sources, "levels": levels}
    except Exception as e:
        return {"logs": [], "total": 0, "limit": limit, "offset": offset, "sources": [], "levels": [], "error": str(e)}


def get_log_detail(db_path: str | Path, log_id: int) -> dict[str, Any] | None:
    """获取单条日志详情。"""
    try:
        conn = _get_conn(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM execution_logs WHERE log_id = ?", (log_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            entry = dict(row)
            if entry.get("metadata"):
                try:
                    entry["metadata"] = json.loads(entry["metadata"])
                except Exception:
                    pass
            return entry
        return None
    except Exception:
        return None


def get_logs_stats(db_path: str | Path) -> dict[str, Any]:
    """日志统计概览。"""
    try:
        conn = _get_conn(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM execution_logs")
        total = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT level, COUNT(*) as cnt FROM execution_logs GROUP BY level ORDER BY cnt DESC"
        )
        by_level = {row["level"]: row["cnt"] for row in cursor.fetchall()}

        cursor.execute(
            "SELECT source, COUNT(*) as cnt FROM execution_logs GROUP BY source ORDER BY cnt DESC"
        )
        by_source = {row["source"]: row["cnt"] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(DISTINCT trace_id) as traces FROM execution_logs WHERE trace_id != ''")
        traces = cursor.fetchone()["traces"]

        cursor.execute(
            "SELECT MAX(timestamp) as last_log FROM execution_logs"
        )
        last_log = cursor.fetchone()["last_log"]

        conn.close()
        return {"total": total, "by_level": by_level, "by_source": by_source, "traces": traces, "last_log": last_log}
    except Exception:
        return {"total": 0, "by_level": {}, "by_source": {}, "traces": 0, "last_log": None}


def delete_log(db_path: str | Path, log_id: int) -> bool:
    """删除单条日志。"""
    try:
        conn = _get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM execution_logs WHERE log_id = ?", (log_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    except Exception:
        return False


def delete_logs_batch(db_path: str | Path, log_ids: list[int]) -> int:
    """批量删除日志，返回实际删除条数。"""
    if not log_ids:
        return 0
    try:
        conn = _get_conn(db_path)
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(log_ids))
        cursor.execute(f"DELETE FROM execution_logs WHERE log_id IN ({placeholders})", log_ids)
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected
    except Exception:
        return 0
