"""SQLite 共享连接工具 — SQLAlchemy 兼容封装。

提供与旧版 sqlite3 接口兼容的 _connect / _SharedConnection / _SharedCursor 等。
从 interfaces/api/services/base.py 提取至此，以消除 application→interfaces 层违例。
"""

from __future__ import annotations

import time
from collections.abc import Mapping as MappingABC
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError

from infrastructure.persistence import database as _db


class _CompatRow(MappingABC):
    """统一行包装：同时支持 row['key'] 和 row[0] 两种索引方式。

    继承 MappingABC 确保 dict(row) 正确产生 {key: value} 字典。
    """

    def __init__(self, row: Any, mapping: Any) -> None:
        self._row = row          # Row — 支持整数索引
        self._mapping = mapping  # RowMapping — 支持字符串键

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


class _RowResult:
    """SQLAlchemy CursorResult → 兼容包装。

    使用 Row 对象（支持 row[0]）+ cursor.description 重建映射（支持 row['key']）。
    """

    def __init__(self, result: Any) -> None:
        self._result = result
        self._rows: list[Any] | None = None
        self._col_names: list[str] = []

    def _ensure(self) -> list[Any]:
        if self._rows is None:
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


class _SharedCursor:
    """兼容 sqlite3.Cursor 的包装。"""

    def __init__(self, session: Any) -> None:
        self._session = session
        self._result: _RowResult | None = None

    def execute(self, sql: str, params: tuple = ()) -> _SharedCursor:
        self._result = _RowResult(_exec_driver(self._session, sql, params))
        return self

    def executemany(self, sql: str, params: list[tuple]) -> None:
        for p in params:
            _exec_driver(self._session, sql, p)

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


class _SharedConnection:
    """独立 Session 包装（兼容旧 _SharedConnection 接口）。

    每次创建获得一个独立 Session，close() 时提交并关闭。
    支持 execute()、cursor()、commit()、rollback()、row_factory 等旧接口。
    """

    def __init__(self, db_path: str | Path) -> None:
        _db.init_engine(db_path)
        self._session = _db.SessionLocal()
        self._closed = False

    def _ensure(self) -> Any:
        if self._closed or self._session is None:
            self._session = _db.SessionLocal()
            self._closed = False
        return self._session

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._session is None:
            return
        try:
            self._session.close()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()

    def cursor(self) -> _SharedCursor:
        return _SharedCursor(self._ensure())

    def execute(self, sql: str, params: tuple = ()) -> _RowResult:
        for attempt in range(3):
            try:
                return _RowResult(_exec_driver(self._ensure(), sql, params))
            except OperationalError as exc:
                if "database is locked" not in str(exc) or attempt == 2:
                    raise
                self.close()
                time.sleep(0.1 * (2**attempt))
        raise RuntimeError("unreachable")

    def executemany(self, sql: str, params: list[tuple]) -> None:
        for attempt in range(3):
            try:
                session = self._ensure()
                for p in params:
                    _exec_driver(session, sql, p)
                return
            except OperationalError as exc:
                if "database is locked" not in str(exc) or attempt == 2:
                    raise
                self.close()
                time.sleep(0.1 * (2**attempt))

    def commit(self) -> None:
        self._ensure().commit()

    def rollback(self) -> None:
        self._ensure().rollback()

    @property
    def row_factory(self) -> Any:
        return None

    @row_factory.setter
    def row_factory(self, value: Any) -> None:
        pass  # SQLAlchemy 通过 .mappings() 处理

    @property
    def total_changes(self) -> int:
        return self._ensure().connection().connection.total_changes  # type: ignore[union-attr]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ensure(), name)


def _connect(db_path: str | Path) -> _SharedConnection:
    """返回 _SharedConnection 实例（兼容旧接口）。"""
    return _SharedConnection(db_path)


def get_conn(db_path: str | Path) -> _SharedConnection:
    """获取连接（与 _connect 等价）。"""
    return _SharedConnection(db_path)


def _get_cursor(db_path: str | Path) -> _SharedCursor:
    """便捷：返回游标。"""
    return _connect(db_path).cursor()
