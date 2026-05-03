"""记忆数据访问服务 — 封装 MemoryService 供 API 路由使用。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from application.services.memory_service import MemoryService
from infrastructure.memory.context_injector import ContextInjector
from infrastructure.memory.flashback_scanner import FlashbackScanner
from infrastructure.persistence.connection import SQLiteConnectionManager
from infrastructure.persistence.memory_repo import MemoryRepository
from infrastructure.vector.chroma_store import ChromaStore
from interfaces.api.services.settings import get_config

_MEMORY_SERVICE_CACHE: dict[str, Any] = {}


def _get_memory_service(db_path: str | Path):
    """懒加载 MemoryService 单例，从 DB 读取记忆配置。"""
    key = str(db_path)
    if key not in _MEMORY_SERVICE_CACHE:
        try:
            # 从 DB 读取记忆配置（若有）
            min_retention = None
            max_memories = None
            try:
                val = get_config(db_path, "memory_min_retention")
                if val:
                    min_retention = float(val)
                val = get_config(db_path, "memory_max_context_memories")
                if val:
                    max_memories = int(val)
            except Exception:
                pass

            conn_mgr = SQLiteConnectionManager(str(db_path))
            chroma = ChromaStore(str(Path(str(db_path)).parent / "chroma"))
            repo = MemoryRepository(conn_mgr, chroma)
            flashback = FlashbackScanner(repo, chroma)
            injector = ContextInjector(repo.search, min_retention=min_retention, max_memories=max_memories, flashback_scanner=flashback)
            _MEMORY_SERVICE_CACHE[key] = MemoryService(repo, injector)
        except Exception:
            _MEMORY_SERVICE_CACHE[key] = None
    return _MEMORY_SERVICE_CACHE.get(key)


def _entry_to_dict(entry) -> dict[str, Any]:
    """将 MemoryEntry 对象转为 dict。"""
    try:
        return {
            "memory_id": entry.memory_id,
            "level": entry.level.value if hasattr(entry.level, "value") else str(entry.level),
            "scope_id": entry.scope_id,
            "content": entry.content,
            "metadata": entry.metadata or {},
            "created_at": entry.created_at.isoformat() if hasattr(entry.created_at, "isoformat") else str(entry.created_at),
            "last_accessed_at": entry.last_accessed_at.isoformat() if hasattr(entry.last_accessed_at, "isoformat") else str(entry.last_accessed_at),
            "access_count": entry.access_count,
            "retention": round(getattr(entry, "retention", 1.0), 4),
            "is_archived": getattr(entry, "is_archived", False),
            "is_important": getattr(entry, "is_important", False),
            "summary": getattr(entry, "summary", None),
        }
    except Exception as e:
        return {"error": str(e)}


def memory_stats(db_path: str | Path) -> dict[str, Any]:
    """获取记忆统计。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return {"total_count": 0, "archived_count": 0, "by_level": {}, "avg_retention": 0, "total_access_count": 0}
    try:
        stats = svc.get_stats()
        return {
            "total_count": stats.total_count,
            "archived_count": stats.archived_count,
            "by_level": stats.by_level,
            "avg_retention": round(stats.avg_retention, 4),
            "total_access_count": stats.total_access_count,
        }
    except Exception:
        return {"total_count": 0, "archived_count": 0, "by_level": {}, "avg_retention": 0, "total_access_count": 0}


def memory_list(
    db_path: str | Path,
    page: int = 1,
    page_size: int = 20,
    level: str | None = None,
    scope_id: str | None = None,
    is_archived: bool | None = None,
    retention_min: float | None = None,
    retention_max: float | None = None,
    keyword: str | None = None,
    sort_by: str = "last_accessed_at",
    sort_desc: bool = True,
) -> dict[str, Any]:
    """分页列出记忆。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
    try:
        entries, total = svc.list_memories(
            level=level, scope_id=scope_id, is_archived=is_archived,
            retention_min=retention_min, retention_max=retention_max,
            keyword=keyword, sort_by=sort_by, sort_desc=sort_desc,
            page=page, page_size=page_size,
        )
        return {
            "items": [_entry_to_dict(e) for e in entries],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    except Exception:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}


def memory_store(db_path: str | Path, content: str, level: str, scope_id: str, metadata: dict | None = None) -> dict[str, Any]:
    """存储一条记忆。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return {"error": "记忆服务不可用"}
    try:
        memory_id = svc.store(content, level, scope_id or "default", metadata or {})
        entry = svc.get(memory_id)
        return _entry_to_dict(entry) if entry else {"memory_id": memory_id}
    except Exception as e:
        return {"error": str(e)}


def memory_get(db_path: str | Path, memory_id: str) -> dict[str, Any] | None:
    """获取单条记忆。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return None
    try:
        entry = svc.get(memory_id)
        return _entry_to_dict(entry) if entry else None
    except Exception:
        return None


def memory_update(db_path: str | Path, memory_id: str, content: str | None = None, metadata: dict | None = None) -> dict[str, Any] | None:
    """更新记忆内容/元数据。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return None
    try:
        entry = svc.update(memory_id, content=content, metadata=metadata)
        return _entry_to_dict(entry) if entry else None
    except Exception:
        return None


def memory_delete(db_path: str | Path, memory_id: str) -> bool:
    """删除记忆。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return False
    try:
        return svc.delete(memory_id)
    except Exception:
        return False


def memory_search(db_path: str | Path, query_text: str, level: str | None = None, scope_id: str | None = None, limit: int = 10, include_archived: bool = True) -> list[dict[str, Any]]:
    """语义搜索记忆。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return []
    try:
        from domain.memory.value_object import MemoryQuery
        query = MemoryQuery(query_text=query_text, level=None, scope_id=scope_id, limit=limit, include_archived=include_archived)
        entries = svc.search(query)
        return [_entry_to_dict(e) for e in entries]
    except Exception:
        return []


def memory_find_by_scope(db_path: str | Path, level: str, scope_id: str) -> list[dict[str, Any]]:
    """按作用域查找记忆。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return []
    try:
        entries = svc.find_by_scope(level, scope_id)
        return [_entry_to_dict(e) for e in entries]
    except Exception:
        return []


def memory_retention(db_path: str | Path, memory_id: str) -> dict[str, Any] | None:
    """获取记忆保留率。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return None
    try:
        retention = svc.calculate_retention(memory_id)
        if retention is None:
            return None
        return {"memory_id": memory_id, "retention": round(retention, 4)}
    except Exception:
        return None


def memory_retention_status(db_path: str | Path, level: str) -> list[dict[str, Any]]:
    """获取某层级所有记忆的保留率。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return []
    try:
        return svc.get_retention_status(level)
    except Exception:
        return []


def memory_archive(db_path: str | Path, threshold: float = 0.15) -> dict[str, Any]:
    """归档低保留率记忆。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return {"archived_count": 0, "threshold": threshold}
    try:
        archived = svc.check_archive(threshold)
        return {"archived_count": len(archived), "threshold": threshold}
    except Exception:
        return {"archived_count": 0, "threshold": threshold}


def memory_unarchive(db_path: str | Path, memory_id: str) -> dict[str, Any] | None:
    """恢复已归档记忆。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return None
    try:
        entry = svc.unarchive(memory_id)
        return _entry_to_dict(entry) if entry else None
    except Exception:
        return None


def memory_batch(db_path: str | Path, action: str, memory_ids: list[str]) -> dict[str, Any]:
    """批量操作记忆 (delete/archive/unarchive)。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return {"action": action, "success_count": 0, "failed_count": len(memory_ids), "errors": ["记忆服务不可用"]}
    success_count = 0
    errors: list[str] = []
    for mid in memory_ids:
        try:
            ok = False
            if action == "delete":
                ok = svc.delete(mid)
            elif action == "archive":
                entry = svc._repo.find_by_id(mid)
                if entry and not entry.is_archived:
                    entry.is_archived = True
                    svc._repo.update(entry)
                    ok = True
            elif action == "unarchive":
                entry = svc.unarchive(mid)
                ok = entry is not None
            if ok:
                success_count += 1
            else:
                errors.append(mid)
        except Exception as e:
            errors.append(f"{mid}: {e}")
    return {"action": action, "success_count": success_count, "failed_count": len(errors), "errors": errors}


def memory_toggle_important(db_path: str | Path, memory_id: str) -> dict[str, Any] | None:
    """切换记忆的重要标记。返回更新后的记忆 dict。"""
    svc = _get_memory_service(db_path)
    if not svc:
        return None
    try:
        entry = svc.get(memory_id)
        if not entry:
            return None
        entry.is_important = not entry.is_important
        # 重要标记切换后重置 retention
        if entry.is_important:
            entry.retention = 1.0
        svc._repo.update(entry)
        return _entry_to_dict(entry)
    except Exception:
        return None
