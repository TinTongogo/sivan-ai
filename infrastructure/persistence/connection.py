"""统一 SQLite 连接管理（SQLAlchemy 管理全部连接）。

对外暴露 SQLiteConnectionManager（单例 + Thread-Local Session）。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping as MappingABC
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError

from config.settings import settings
from infrastructure.persistence import database as _db


class _CompatRow(MappingABC):
    """统一行包装：同时支持 row['key'] 和 row[0] 两种索引方式。"""

    def __init__(self, row: Any, mapping: dict[str, Any]) -> None:
        self._row = row
        self._mapping = mapping

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, (int, slice)):
            return self._row[key]
        return self._mapping[key]

    def __iter__(self) -> Any:
        return iter(self._mapping)

    def __len__(self) -> int:
        return len(self._row)

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except (KeyError, IndexError, TypeError):
            return default


def _exec_driver(session: Any, sql: str, params: Any = ()) -> Any:
    """通过底层 DBAPI 连接执行 SQL（支持 ? 风格参数）。

    自动将 list[str|int] 转为 tuple，避免 SQLAlchemy 误判为 executemany 参数。
    """
    if isinstance(params, list) and params and not isinstance(params[0], (tuple, dict)):
        params = tuple(params)
    return session.connection().exec_driver_sql(sql, params)


class _RowProxyResult:
    """SQLAlchemy CursorResult → 兼容包装。

    使用 Row 对象（支持 row[0]）+ cursor.description 重建映射（支持 row['key']）。
    """

    def __init__(self, result: Any) -> None:
        self._result = result
        self._rows: list[Any] | None = None
        self._col_names: list[str] = []

    def _ensure(self) -> list[Any]:
        if self._rows is None:
            # 在消费结果前获取 cursor.description
            try:
                self._col_names = [col[0] for col in self._result.cursor.description]
            except Exception:
                self._col_names = []
            self._rows = list(self._result.fetchall())
        return self._rows

    def _compat(self, row: Any) -> _CompatRow:
        return _CompatRow(row, {n: row[i] for i, n in enumerate(self._col_names)})

    def fetchone(self) -> Any | None:
        rows = self._ensure()
        return self._compat(rows[0]) if rows else None

    def fetchall(self) -> list[Any]:
        self._ensure()
        return [self._compat(r) for r in self._rows]

    @property
    def lastrowid(self) -> int | None:
        return self._result.lastrowid

    @property
    def rowcount(self) -> int:
        return self._result.rowcount

    def __iter__(self) -> Any:
        return iter(self.fetchall())


class _ConnectionProxy:
    """模拟 sqlite3.Connection，供 Agent 等需要原生连接对象的场景使用。"""

    def __init__(self, mgr: SQLiteConnectionManager) -> None:
        self._mgr = mgr

    def cursor(self) -> _ConnectionProxyCursor:
        return _ConnectionProxyCursor(self._mgr)

    def execute(self, sql: str, params: tuple = ()) -> _RowProxyResult:
        return self._mgr.execute(sql, params)

    def commit(self) -> None:
        self._mgr.commit()

    def close(self) -> None:
        self._mgr.close()


class _ConnectionProxyCursor:
    def __init__(self, mgr: SQLiteConnectionManager) -> None:
        self._mgr = mgr
        self._result: _RowProxyResult | None = None

    def execute(self, sql: str, params: tuple = ()) -> _ConnectionProxyCursor:
        self._result = self._mgr.execute(sql, params)
        return self

    @property
    def lastrowid(self) -> int | None:
        return self._result.lastrowid if self._result else None

    @property
    def rowcount(self) -> int:
        return self._result.rowcount if self._result else 0

    def fetchone(self) -> Any | None:
        return self._result.fetchone() if self._result else None

    def fetchall(self) -> list[Any]:
        return self._result.fetchall() if self._result else []


class SQLiteConnectionManager:
    """SQLite 连接管理器（单例 + Thread-Local Session）。

    与旧版接口完全兼容。内部使用 SQLAlchemy Engine + QueuePool + Session。
    """

    _instance: SQLiteConnectionManager | None = None
    _lock = threading.Lock()
    _local = threading.local()

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or settings.DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls, db_path: str | Path | None = None) -> SQLiteConnectionManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    def _close_session(self) -> None:
        """关闭当前线程的 Session 并清空 thread-local。"""
        session = getattr(self._local, "session", None)
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
            self._local.session = None

    def _get_session(self, *, fresh: bool = False) -> Any:
        """获取当前线程的 Session（延迟创建）。

        fresh=True 时强制创建新 Session（丢弃旧的）。
        """
        if fresh:
            self._close_session()
        session = getattr(self._local, "session", None)
        if session is None:
            _db.init_engine(self.db_path)
            session = _db.SessionLocal()
            self._local.session = session
        return session

    @property
    def connection(self) -> _ConnectionProxy:
        """返回兼容 sqlite3.Connection 的代理对象。"""
        return _ConnectionProxy(self)

    def execute(self, sql: str, params: tuple = ()) -> _RowProxyResult:
        """执行 SQL，遇到 'database is locked' 自动重试。"""
        for attempt in range(3):
            try:
                return _RowProxyResult(
                    _exec_driver(self._get_session(fresh=(attempt > 0)), sql, params)
                )
            except OperationalError as exc:
                if "database is locked" not in str(exc) or attempt == 2:
                    raise
                time.sleep(0.1 * (2**attempt))
        raise RuntimeError("unreachable")

    def executemany(self, sql: str, params: list[tuple]) -> None:
        for attempt in range(3):
            try:
                session = self._get_session(fresh=(attempt > 0))
                for p in params:
                    _exec_driver(session, sql, p)
                return
            except OperationalError as exc:
                if "database is locked" not in str(exc) or attempt == 2:
                    raise
                time.sleep(0.1 * (2**attempt))

    def commit(self) -> None:
        """提交当前线程的事务并关闭 Session。"""
        session = getattr(self._local, "session", None)
        if session is not None:
            try:
                session.commit()
            finally:
                try:
                    session.close()
                except Exception:
                    pass
                self._local.session = None

    def close(self) -> None:
        self.commit()

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）。"""
        with cls._lock:
            cls._instance = None


def _wal_connect(db_path: str | Path) -> Any:
    """获取原生 DBAPI 连接（通过 SQLAlchemy 引擎池管理）。"""
    _db.init_engine(db_path)
    conn = _db.engine.raw_connection()
    # SQLAlchemy engine 的 connect 事件已处理 WAL/Pragma，
    # 只需为向下兼容设置 row_factory
    import sqlite3
    conn.driver_connection.row_factory = sqlite3.Row
    return conn
