"""本能模板数据访问服务 — 封装 InstinctRepository 供 API 路由使用。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _get_instinct_repo(db_path: str | Path):
    """懒加载 InstinctRepository。"""
    try:
        from infrastructure.memory.instinct_repo import InstinctRepository
        from infrastructure.persistence.connection import SQLiteConnectionManager
        cm = SQLiteConnectionManager(str(db_path))
        return InstinctRepository(cm)
    except Exception:
        return None


def instinct_list(db_path: str | Path, page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """分页列出所有本能模板。"""
    repo = _get_instinct_repo(db_path)
    if not repo:
        return {"items": [], "total": 0}
    try:
        patterns, total = repo.find_all(page=page, page_size=page_size)
        return {
            "items": [p.to_dict() for p in patterns],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception:
        return {"items": [], "total": 0}


def instinct_get(db_path: str | Path, pattern_id: str) -> dict[str, Any] | None:
    """获取单个本能模板。"""
    repo = _get_instinct_repo(db_path)
    if not repo:
        return None
    try:
        pattern = repo.find_by_id(pattern_id)
        return pattern.to_dict() if pattern else None
    except Exception:
        return None


def instinct_toggle_active(db_path: str | Path, pattern_id: str) -> dict[str, Any] | None:
    """切换本能模板的激活状态。"""
    repo = _get_instinct_repo(db_path)
    if not repo:
        return None
    try:
        pattern = repo.find_by_id(pattern_id)
        if not pattern:
            return None
        pattern.is_active = not pattern.is_active
        repo.update(pattern)
        return pattern.to_dict()
    except Exception:
        return None


def instinct_delete(db_path: str | Path, pattern_id: str) -> bool:
    """删除本能模板。"""
    repo = _get_instinct_repo(db_path)
    if not repo:
        return False
    try:
        return repo.delete(pattern_id)
    except Exception:
        return False


def instinct_stats(db_path: str | Path) -> dict[str, Any]:
    """本能模板统计。"""
    repo = _get_instinct_repo(db_path)
    if not repo:
        return {"total": 0, "active": 0, "by_type": {}}
    try:
        patterns = repo.find_all()[0]
        total = len(patterns)
        active = sum(1 for p in patterns if p.is_active)
        by_type: dict[str, int] = {}
        for p in patterns:
            by_type[p.task_type] = by_type.get(p.task_type, 0) + 1
        return {"total": total, "active": active, "by_type": by_type}
    except Exception:
        return {"total": 0, "active": 0, "by_type": {}}
