"""配置管理服务层 — 操作 settings 表和 llm_providers 表。"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from config.settings import settings
from interfaces.api.services.base import get_conn as _get_shared_conn

logger = logging.getLogger(__name__)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    """返回共享连接包装（忽略 close）。"""
    return _get_shared_conn(db_path)


# ── 默认配置种子数据 ──────────────────────────────────────────

DEFAULT_SETTINGS: dict[str, dict[str, str]] = {
    # ── LLM ──
    "llm_provider": {
        "value": "anthropic",
        "value_type": "str",
        "description": "LLM 提供商 (anthropic, ollama, deepseek, openai)",
        "category": "llm",
    },
    "llm_api_key": {
        "value": "",
        "value_type": "str",
        "description": "LLM API Key",
        "category": "llm",
    },
    "llm_api_url": {
        "value": "https://api.anthropic.com/v1/messages",
        "value_type": "str",
        "description": "LLM API URL",
        "category": "llm",
    },
    "llm_model": {
        "value": "claude-sonnet-4-20250514",
        "value_type": "str",
        "description": "LLM 模型名称",
        "category": "llm",
    },
    "llm_max_tokens": {
        "value": "4096",
        "value_type": "int",
        "description": "最大输出 Token 数",
        "category": "llm",
    },
    "llm_temperature": {
        "value": "0.7",
        "value_type": "float",
        "description": "温度参数 (0.0-2.0)",
        "category": "llm",
    },
    "llm_timeout": {
        "value": "120",
        "value_type": "int",
        "description": "请求超时 (秒)",
        "category": "llm",
    },
    "llm_api_version": {
        "value": "2023-06-01",
        "value_type": "str",
        "description": "API 版本 (仅 Anthropic)",
        "category": "llm",
    },

    # ── SMTP ──
    "smtp_host": {
        "value": settings.SMTP_HOST,
        "value_type": "str",
        "description": "SMTP 服务器地址",
        "category": "smtp",
    },
    "smtp_port": {
        "value": str(settings.SMTP_PORT),
        "value_type": "int",
        "description": "SMTP 端口",
        "category": "smtp",
    },
    "smtp_username": {
        "value": settings.SMTP_USERNAME,
        "value_type": "str",
        "description": "SMTP 用户名",
        "category": "smtp",
    },
    "smtp_password": {
        "value": settings.SMTP_PASSWORD,
        "value_type": "str",
        "description": "SMTP 密码",
        "category": "smtp",
    },
    "smtp_from": {
        "value": settings.SMTP_FROM_ADDRESS,
        "value_type": "str",
        "description": "发件人地址",
        "category": "smtp",
    },

    # ── Memory ──
    "memory_session_ttl": {
        "value": str(settings.MEMORY_SESSION_TTL),
        "value_type": "int",
        "description": "会话记忆 TTL (秒)",
        "category": "memory",
    },
    "memory_session_max_size": {
        "value": str(settings.MEMORY_SESSION_MAX_SIZE),
        "value_type": "int",
        "description": "会话记忆最大条数",
        "category": "memory",
    },
    "memory_min_retention": {
        "value": str(settings.MEMORY_DEFAULT_MIN_RETENTION),
        "value_type": "float",
        "description": "检索最低保留率",
        "category": "memory",
    },
    "memory_archive_threshold": {
        "value": str(settings.MEMORY_ARCHIVE_THRESHOLD),
        "value_type": "float",
        "description": "归档阈值",
        "category": "memory",
    },
    "memory_max_context_memories": {
        "value": str(settings.MEMORY_MAX_CONTEXT_MEMORIES),
        "value_type": "int",
        "description": "上下文注入最大条数",
        "category": "memory",
    },

    # ── Auth ──
    "auth_cookie_name": {
        "value": settings.AUTH_COOKIE_NAME,
        "value_type": "str",
        "description": "认证 Cookie 名称",
        "category": "auth",
    },
    "auth_cookie_max_age": {
        "value": str(settings.AUTH_COOKIE_MAX_AGE),
        "value_type": "int",
        "description": "认证 Cookie 有效期 (秒)",
        "category": "auth",
    },
    "auth_salt": {
        "value": settings.AUTH_SALT,
        "value_type": "str",
        "description": "认证哈希盐值",
        "category": "auth",
    },

    # ── RAG ──
    "rag_chunk_size": {
        "value": "500",
        "value_type": "int",
        "description": "文档分块大小（字符数）",
        "category": "rag",
    },
    "rag_chunk_overlap": {
        "value": "50",
        "value_type": "int",
        "description": "分块重叠字符数",
        "category": "rag",
    },
    "rag_embedding_model": {
        "value": "BAAI/bge-small-zh-v1.5",
        "value_type": "str",
        "description": "Embedding 模型名称",
        "category": "rag",
    },
    "rag_default_top_k": {
        "value": "5",
        "value_type": "int",
        "description": "检索默认返回条数",
        "category": "rag",
    },
}


def init_default_settings(db_path: str | Path) -> None:
    """初始化默认配置项（仅插入不存在的键）。"""
    conn = _connect(db_path)
    cursor = conn.cursor()
    for key, cfg in DEFAULT_SETTINGS.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value, value_type, description, category) "
            "VALUES (?, ?, ?, ?, ?)",
            (key, cfg["value"], cfg["value_type"], cfg["description"], cfg["category"]),
        )
    conn.commit()
    conn.close()


def get_all_settings(db_path: str | Path) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings ORDER BY category, key")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_setting(db_path: str | Path, key: str) -> dict[str, Any] | None:
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def set_setting(
    db_path: str | Path,
    key: str,
    value: str,
    value_type: str | None = None,
    description: str | None = None,
    category: str | None = None,
) -> None:
    conn = _connect(db_path)
    cursor = conn.cursor()
    existing = cursor.execute("SELECT * FROM settings WHERE key = ?", (key,)).fetchone()
    if existing:
        cursor.execute(
            "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
            (value, key),
        )
    else:
        cursor.execute(
            "INSERT INTO settings (key, value, value_type, description, category) VALUES (?, ?, ?, ?, ?)",
            (key, value, value_type or "str", description or "", category or "general"),
        )
    conn.commit()
    conn.close()


def delete_setting(db_path: str | Path, key: str) -> bool:
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_settings_by_category(db_path: str | Path, category: str) -> list[dict[str, Any]]:
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings WHERE category = ? ORDER BY key", (category,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_config(db_path: str | Path, key: str, default: str | None = None) -> str | None:
    """从 DB settings 表读取配置值。"""
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["value"]
    return default


def get_configs_by_category(db_path: str | Path, category: str) -> dict[str, str]:
    """获取某分类下所有配置的 key-value dict。"""
    rows = get_settings_by_category(db_path, category)
    return {r["key"]: r["value"] for r in rows}


def get_llm_settings(db_path: str | Path) -> dict[str, str]:
    """获取 LLM 配置，缺失项使用硬编码默认值。"""
    rows = get_settings_by_category(db_path, "llm")
    result: dict[str, str] = {}
    for r in rows:
        result[r["key"]] = r["value"]

    env_fallbacks: dict[str, str] = {
        "llm_api_key": "",
        "llm_api_url": "https://api.anthropic.com/v1/messages",
        "llm_model": "claude-sonnet-4-20250514",
        "llm_max_tokens": "4096",
        "llm_temperature": "0.7",
        "llm_timeout": "120",
        "llm_api_version": "2023-06-01",
    }
    for key, fallback in env_fallbacks.items():
        if key not in result or not result[key]:
            result[key] = fallback

    if "llm_provider" not in result or not result["llm_provider"]:
        result["llm_provider"] = "anthropic"

    return result


# ═══════════════════════════════════════════════════════════════
# 动态 LLM 提供商 CRUD
# ═══════════════════════════════════════════════════════════════

_PROVIDER_FIELDS = [
    "name", "auth_type", "api_url", "api_key", "model",
    "api_version", "max_tokens", "temperature", "timeout", "is_active",
]


def get_providers(db_path: str | Path) -> list[dict[str, Any]]:
    """获取所有 LLM 提供商（隐藏 api_key 值，仅暴露 has_api_key）。"""
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM llm_providers ORDER BY created_at ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    for r in rows:
        r["has_api_key"] = bool(r.get("api_key"))
        r["api_key"] = ""
    return rows


def get_provider_by_id(db_path: str | Path, provider_id: str) -> dict[str, Any] | None:
    """获取单个提供商（含 api_key）。"""
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM llm_providers WHERE id = ?", (provider_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_provider(db_path: str | Path) -> dict[str, Any] | None:
    """获取当前激活的提供商。"""
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_provider(
    db_path: str | Path,
    name: str,
    auth_type: str = "OpenAI",
    api_url: str = "",
    api_key: str = "",
    model: str = "",
    api_version: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    timeout: int = 120,
) -> dict[str, Any]:
    """创建新的 LLM 提供商。"""
    import uuid

    pid = str(uuid.uuid4())[:8]
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO llm_providers
           (id, name, auth_type, api_url, api_key, model, api_version,
            max_tokens, temperature, timeout, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
        (pid, name, auth_type, api_url, api_key, model, api_version,
         max_tokens, temperature, timeout),
    )
    conn.commit()
    conn.close()
    return {"id": pid, "name": name, "auth_type": auth_type, "has_api_key": bool(api_key)}


def update_provider(db_path: str | Path, provider_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """更新提供商字段。返回更新后的记录（api_key 隐藏）。"""
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM llm_providers WHERE id = ?", (provider_id,))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        return None

    pairs: list[str] = []
    values: list[Any] = []
    for field in _PROVIDER_FIELDS:
        if field in data:
            pairs.append(f"{field} = ?")
            values.append(data[field])
    if not pairs:
        conn.close()
        result = dict(existing)
        result["has_api_key"] = bool(result.get("api_key"))
        result["api_key"] = ""
        return result

    pairs.append("updated_at = CURRENT_TIMESTAMP")
    values.append(provider_id)
    cursor.execute(f"UPDATE llm_providers SET {', '.join(pairs)} WHERE id = ?", values)
    conn.commit()

    cursor.execute("SELECT * FROM llm_providers WHERE id = ?", (provider_id,))
    row = cursor.fetchone()
    conn.close()
    result = dict(row) if row else None
    if result:
        if result.get("is_active"):
            _sync_llm_settings(db_path, result)
        result["has_api_key"] = bool(result.get("api_key"))
        result["api_key"] = ""
    return result


def delete_provider(db_path: str | Path, provider_id: str) -> bool:
    """删除提供商（激活中的不可删除）。"""
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM llm_providers WHERE id = ?", (provider_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    if row["is_active"]:
        conn.close()
        return False
    cursor.execute("DELETE FROM llm_providers WHERE id = ?", (provider_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def activate_provider(db_path: str | Path, provider_id: str) -> dict[str, Any] | None:
    """设为激活，取消其他提供商的激活状态。"""
    conn = _connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE llm_providers SET is_active = 0")
    cursor.execute(
        "UPDATE llm_providers SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (provider_id,),
    )
    cursor.execute("SELECT * FROM llm_providers WHERE id = ?", (provider_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()
    result = dict(row) if row else None
    if result:
        _sync_llm_settings(db_path, result)
        result["has_api_key"] = bool(result.get("api_key"))
        result["api_key"] = ""
    return result


def _sync_llm_settings(db_path: str | Path, provider: dict[str, Any]) -> None:
    """同步激活的提供商配置到旧 settings 表，保证全部配置页面数据一致。"""
    mapping = {
        "llm_provider": ("name", str),
        "llm_api_url": ("api_url", str),
        "llm_api_key": ("api_key", str),
        "llm_model": ("model", str),
        "llm_api_version": ("api_version", str),
        "llm_max_tokens": ("max_tokens", str),
        "llm_temperature": ("temperature", str),
        "llm_timeout": ("timeout", str),
    }
    conn = _connect(db_path)
    cursor = conn.cursor()
    for setting_key, (provider_field, cast) in mapping.items():
        val = provider.get(provider_field)
        if val is not None:
            cursor.execute(
                "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = ?",
                (cast(val), setting_key),
            )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
# 测试连接
# ═══════════════════════════════════════════════════════════════


def test_llm_connection_with_provider(provider: dict[str, Any]) -> dict[str, Any]:
    """测试 LLM 连接（基于提供商 dict，不读 DB）。"""
    if not provider.get("api_url"):
        return {"success": False, "error": "API URL 未配置"}
    try:
        from infrastructure.llm.factory import create_llm_provider
        llm = create_llm_provider(provider)
        return llm.test_connection()
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_llm_connection(db_path: str | Path) -> dict[str, Any]:
    """测试当前激活的 LLM 连接。"""
    provider = get_active_provider(db_path)
    if not provider:
        return {"success": False, "error": "未找到激活的 LLM 提供商，请先在设置中配置"}
    return test_llm_connection_with_provider(provider)


# ═══════════════════════════════════════════════════════════════
# 模型列表获取
# ═══════════════════════════════════════════════════════════════


def fetch_llm_models_for_provider(provider: dict[str, Any]) -> list[str]:
    """获取提供商的可用模型列表。"""
    try:
        from infrastructure.llm.factory import create_llm_provider
        llm = create_llm_provider(provider)
        return llm.list_models()
    except Exception as e:
        logger.warning("获取模型列表失败: %s", e)
        return []


def fetch_llm_models(db_path: str | Path, provider_name: str | None = None) -> list[str]:
    """获取当前激活（或按名称匹配）提供商的模型列表（向后兼容）。"""
    if provider_name:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM llm_providers WHERE name = ?", (provider_name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return fetch_llm_models_for_provider(dict(row))
        return []
    active = get_active_provider(db_path)
    if active:
        return fetch_llm_models_for_provider(active)
    return []


def init_default_project(db_path: str | Path) -> None:
    """初始化默认项目记录。"""
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM projects WHERE project_id = 'default'")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO projects (project_id, name, description, status, created_by) VALUES (?, ?, ?, ?, ?)",
                ("default", "默认项目", "系统默认项目", "active", "system"),
            )
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

