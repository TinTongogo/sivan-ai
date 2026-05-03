"""通用辅助 — 共享数据库连接工具（SQLAlchemy 适配层）。

对外暴露与旧版完全相同的接口（_SharedConnection、_connect、get_conn），
内部使用 SQLAlchemy Session。

⚠️ 此为向后兼容的重导出层，实际实现在 infrastructure/persistence/shared_connection.py。
新代码应直接从 infrastructure.persistence.shared_connection 导入。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infrastructure.persistence.shared_connection import (
    _connect,
    _get_cursor,
    _SharedConnection,
    _SharedCursor,
    get_conn,
)

__all__ = [
    "_connect", "_get_cursor", "_SharedConnection", "_SharedCursor", "get_conn",
]
