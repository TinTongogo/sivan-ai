"""会话级记忆存储 (内存中，短期)。

使用字典存储 session 级记忆，1 小时 TTL 自动过期。
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class SessionMemory:
    """会话级记忆存储。

    纯内存实现，每条记忆带 TTL (默认 1 小时)，
    超过 TTL 自动过期，支持 LRU 淘汰。
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600) -> None:
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl  # 1 hour

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """存储会话记忆。"""
        self._evict_expired()
        expiry = time.time() + (ttl if ttl is not None else self._default_ttl)
        self._store[key] = (value, expiry)
        self._store.move_to_end(key)

        if len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def get(self, key: str) -> Any | None:
        """获取会话记忆，已过期返回 None。"""
        self._evict_expired()
        if key not in self._store:
            return None
        value, expiry = self._store[key]
        if time.time() > expiry:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def delete(self, key: str) -> bool:
        """删除会话记忆。"""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """清空所有会话记忆。"""
        self._store.clear()

    def clear_session(self, session_id: str) -> None:
        """清空指定会话前缀的所有记忆。"""
        prefix = f"session:{session_id}:"
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]

    def get_all(self, scope_prefix: str | None = None) -> list[tuple[str, Any]]:
        """获取所有未过期的记忆。"""
        self._evict_expired()
        now = time.time()
        results = []
        for key, (value, expiry) in self._store.items():
            if now <= expiry:
                if scope_prefix is None or key.startswith(scope_prefix):
                    results.append((key, value))
        return results

    @property
    def size(self) -> int:
        self._evict_expired()
        return len(self._store)

    def _evict_expired(self) -> None:
        """淘汰过期记忆。"""
        now = time.time()
        expired_keys = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired_keys:
            del self._store[k]
