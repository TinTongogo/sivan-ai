"""系统统计服务。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from interfaces.api.services.agents import get_agents_count
from interfaces.api.services.contracts import get_contracts_count
from interfaces.api.services.logs import get_logs_stats
from interfaces.api.services.memory import memory_stats
from interfaces.api.services.routing import get_routing_stats, get_routing_stats_summary
from interfaces.api.services.skills import get_skills_count, get_skills_stats
from interfaces.api.services.squads import get_squads_stats
from interfaces.api.services.tokens import get_token_stats, get_token_stats_summary
from interfaces.api.services.base import _connect


def _get_kb_count(db_path: str | Path) -> int:
    """获取知识库总数。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM knowledge_bases")
        return cursor.fetchone()["cnt"]
    except Exception:
        return 0


def _get_conversations_count(db_path: str | Path) -> int:
    """获取对话总数。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM conversations")
        return cursor.fetchone()["cnt"]
    except Exception:
        return 0


def _get_reports_count(db_path: str | Path) -> int:
    """获取周报总数。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM weekly_reports")
        return cursor.fetchone()["cnt"]
    except Exception:
        return 0


def _get_settings_count(db_path: str | Path) -> dict[str, int]:
    """获取配置项和提供商数量。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM settings")
        settings_cnt = cursor.fetchone()["cnt"]
        cursor.execute("SELECT COUNT(*) as cnt FROM llm_providers")
        providers_cnt = cursor.fetchone()["cnt"]
        conn.close()
        return {"settings": settings_cnt, "providers": providers_cnt}
    except Exception:
        return {"settings": 0, "providers": 0}


def get_system_stats(db_path: str | Path) -> dict[str, Any]:
    """获取系统统计总览。"""
    squads = get_squads_stats(db_path)
    logs = get_logs_stats(db_path)
    mem = memory_stats(db_path)
    contracts = get_contracts_count(db_path)
    skills_cnt = get_skills_count(db_path)
    skills_detail = get_skills_stats(db_path)
    routing_detail = get_routing_stats(db_path)
    token_detail = get_token_stats(db_path)
    sq_total = squads.get("total_executions", 0) or 0
    sq_succ = squads.get("total_successes", 0) or 0
    return {
        "timestamp": datetime.now().isoformat(),
        "system": {
            "name": "Sivan 你的私人 AI 团队",
            "version": "v1.0.0",
            "status": "运行中",
        },
        "agents": get_agents_count(db_path),
        "contracts": contracts,
        "routing": {
            **get_routing_stats_summary(db_path),
            "by_strategy": routing_detail.get("by_strategy", {}),
            "by_agent": dict(list(routing_detail.get("by_agent", {}).items())[:5]),
        },
        "tokens": {
            **get_token_stats_summary(db_path),
            "total_input": token_detail.get("total", {}).get("total_input", 0),
            "total_output": token_detail.get("total", {}).get("total_output", 0),
            "total_requests": token_detail.get("total", {}).get("total_requests", 0),
            "by_model": dict(list(token_detail.get("by_model", {}).items())[:5]),
        },
        "skills": {
            **skills_cnt,
            "by_frequency": skills_detail.get("by_frequency", {}),
        },
        "squads": {
            "total": squads.get("total", 0),
            "by_status": squads.get("by_status", {}),
            "by_category": squads.get("by_category", {}),
            "total_executions": sq_total,
            "total_successes": sq_succ,
            "success_rate": (sq_succ / sq_total * 100) if sq_total > 0 else 0,
            "most_active": squads.get("most_active", []),
            "most_successful": squads.get("most_successful", []),
        },
        "memory": {
            "total": mem.get("total_count", 0),
            "archived": mem.get("archived_count", 0),
            "by_level": mem.get("by_level", {}),
            "avg_retention": mem.get("avg_retention", 0),
            "total_access_count": mem.get("total_access_count", 0),
        },
        "logs": {
            "total": logs.get("total", 0),
            "by_level": logs.get("by_level", {}),
            "traces": logs.get("traces", 0),
            "last_log": logs.get("last_log"),
        },
        "knowledge_bases": {
            "total": _get_kb_count(db_path),
        },
        "conversations": {
            "total": _get_conversations_count(db_path),
        },
        "reports": {
            "total": _get_reports_count(db_path),
        },
        "settings": _get_settings_count(db_path),
    }
