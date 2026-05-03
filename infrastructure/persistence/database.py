"""SQLAlchemy 数据库引擎与会话管理。

单例 Engine + QueuePool，使用 WAL 模式解决 SQLite 并发写入冲突。
每个线程通过 get_session() 上下文管理器获取独立 Session。
"""

from __future__ import annotations

import functools
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import QueuePool

from config.settings import settings

engine: Engine | None = None
SessionLocal: Any = None  # sessionmaker — 延迟初始化


def _set_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
    """新连接建立时设置 WAL 模式 pragma。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-8000")
    cursor.close()


def init_engine(db_path: str | Path | None = None) -> Engine:
    """初始化全局 SQLAlchemy Engine（单例，重复调用只初始化一次）。"""
    global engine, SessionLocal
    if engine is not None:
        return engine

    db_path = Path(db_path or settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"sqlite:///{db_path}"

    engine = create_engine(
        url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 5},
        echo=False,
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)

    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=engine)
    return engine


def get_engine() -> Engine:
    """获取全局 Engine（延迟初始化）。"""
    if engine is None:
        return init_engine()
    return engine


@contextmanager
def get_session() -> Iterator[Any]:
    """获取数据库 Session 的上下文管理器。

    退出时自动 commit（成功）或 rollback（异常），自动 close。
    """
    init_engine()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_session_with_retry(max_retries: int = 3, delay: float = 0.1) -> Iterator[Any]:
    """带退避重试的 Session 上下文管理器。

    遇到 "database is locked" 错误时指数退避重试。
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            with get_session() as session:
                yield session
            return
        except OperationalError as exc:
            if "database is locked" in str(exc):
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(delay * (2**attempt))
                    continue
            raise
    raise last_exc  # type: ignore[misc]


def retry_on_lock(max_retries: int = 3, delay: float = 0.1):
    """装饰器：遇到 'database is locked' 时自动重试。"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as exc:
                    if "database is locked" in str(exc):
                        last_exc = exc
                        if attempt < max_retries - 1:
                            time.sleep(delay * (2**attempt))
                            continue
                    raise
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator
