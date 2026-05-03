"""结构化日志的 DB 写入层。

将关键节点日志写入 execution_logs 表，通过 trace_id 关联同一执行流。
每次调用创建独立连接，写完后立即关闭，避免连接泄漏和写锁冲突。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


class DbLogger:
    """写入 execution_logs 表的结构化日志器（每调用创建独立连接）。"""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def _connect(self) -> Any:
        """从 SQLAlchemy 引擎池获取独立连接。"""
        from infrastructure.persistence.connection import _wal_connect
        return _wal_connect(self._db_path)

    def log(
        self,
        level: str,
        source: str,
        action: str,
        message: str,
        trace_id: str = "",
        parent_log_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        project_id: str = "",
        duration_ms: int = 0,
    ) -> int | None:
        """写一条日志到 execution_logs。"""
        conn = None
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO execution_logs
                   (trace_id, parent_log_id, level, source, action, message, metadata, project_id, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trace_id or "",
                    parent_log_id,
                    level,
                    source,
                    action,
                    message,
                    json.dumps(metadata, ensure_ascii=False) if metadata else "{}",
                    project_id,
                    duration_ms,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception:
            return None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def trace(
        self,
        source: str,
        action: str,
        message: str,
        metadata: dict[str, Any] | None = None,
        project_id: str = "",
        trace_id: str = "",
    ) -> tuple[str, int | None]:
        """快捷方法：生成 trace_id 并以 INFO 级别落一条日志。

        若传入 trace_id 则复用（续接上游链路），否则自动生成新的。
        """
        if not trace_id:
            trace_id = uuid.uuid4().hex[:16]
        log_id = self.log("INFO", source, action, message, trace_id=trace_id, metadata=metadata, project_id=project_id)
        return trace_id, log_id


_logger: DbLogger | None = None


def init_db_logger(db_path: str | Path) -> DbLogger:
    global _logger
    _logger = DbLogger(db_path)
    return _logger


def get_db_logger() -> DbLogger:
    if _logger is None:
        from config.settings import settings
        init_db_logger(settings.DB_PATH)
    return _logger  # type: ignore[return-value]
