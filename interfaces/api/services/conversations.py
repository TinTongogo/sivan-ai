"""对话与消息服务 — CRUD 操作。

职责范围：
  - Conversation CRUD（create / list / get / update / delete / copy）
  - Message   CRUD（list / create / update / get / delete / has_running）
  - Conversation-Agent 跟踪

执行编排逻辑已移至 interfaces/api/services/execution.py。

分层：
  - 本模块保持与 routes 一致的函数签名（db_path 参数）
  - 内部委托 infrastructure/persistence/conversation_repo.py 的仓库类
"""

from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any

from infrastructure.persistence.conversation_repo import (
    ConversationAgentRepository,
    ConversationRepository,
    MessageRepository,
)

logger = getLogger("sivan.conversations")


# ── 内部辅助 ──────────────────────────────────────────────────────


def _get_repos(db_path: str | Path) -> tuple[ConversationRepository, MessageRepository, ConversationAgentRepository]:
    """从 db_path 快速构建三个仓库实例（使用 SQLiteConnectionManager 单例）。"""
    from infrastructure.persistence.connection import SQLiteConnectionManager

    mgr = SQLiteConnectionManager.get_instance(str(db_path))
    return (
        ConversationRepository(mgr),
        MessageRepository(mgr),
        ConversationAgentRepository(mgr),
    )


# ── Conversation CRUD ────────────────────────────────────────────


def create_conversation(db_path: str | Path, title: str = "新对话", project_id: str = "default") -> dict[str, Any]:
    repo, _, _ = _get_repos(db_path)
    return repo.create(title=title, project_id=project_id)


def list_conversations(
    db_path: str | Path, page: int = 1, page_size: int = 20, project_id: str | None = None
) -> dict[str, Any]:
    repo, _, _ = _get_repos(db_path)
    return repo.find_all(page=page, page_size=page_size, project_id=project_id)


def get_conversation(db_path: str | Path, conversation_id: str) -> dict[str, Any] | None:
    repo, _, _ = _get_repos(db_path)
    return repo.find_by_id(conversation_id)


def update_conversation(db_path: str | Path, conversation_id: str, title: str | None = None) -> bool:
    repo, _, _ = _get_repos(db_path)
    return repo.update(conversation_id, title=title)


def delete_conversation(db_path: str | Path, conversation_id: str) -> bool:
    repo, _, _ = _get_repos(db_path)
    return repo.delete(conversation_id)


def copy_conversation(db_path: str | Path, conversation_id: str, new_title: str | None = None) -> dict[str, Any] | None:
    repo, _, _ = _get_repos(db_path)
    return repo.copy(conversation_id, new_title=new_title)


# ── Message CRUD ─────────────────────────────────────────────────


def list_messages(db_path: str | Path, conversation_id: str) -> list[dict[str, Any]]:
    _, repo, _ = _get_repos(db_path)
    return repo.find_by_conversation(conversation_id)


def has_running_message(db_path: str | Path, conversation_id: str) -> bool:
    _, repo, _ = _get_repos(db_path)
    return repo.has_running(conversation_id)


def create_message(
    db_path: str | Path,
    conversation_id: str,
    role: str,
    content: str,
    *,
    parent_id: str | None = None,
    agent_name: str | None = None,
    status: str = "completed",
    metadata: dict | None = None,
) -> dict[str, Any]:
    _, repo, _ = _get_repos(db_path)
    return repo.create(
        conversation_id, role, content, parent_id=parent_id, agent_name=agent_name, status=status, metadata=metadata
    )


def update_message_status(
    db_path: str | Path,
    message_id: str,
    status: str,
    content: str | None = None,
    agent_name: str | None = None,
    metadata: dict | None = None,
    trace_id: str = "",
) -> bool:
    _, repo, _ = _get_repos(db_path)
    repo.update_status(message_id, status, content=content, agent_name=agent_name, metadata=metadata, trace_id=trace_id)
    return True


def get_message(db_path: str | Path, message_id: str) -> dict[str, Any] | None:
    _, repo, _ = _get_repos(db_path)
    return repo.find_by_id(message_id)


def delete_message(db_path: str | Path, message_id: str) -> bool:
    _, repo, _ = _get_repos(db_path)
    return repo.delete(message_id)


# ── Conversation-Agent tracking ──────────────────────────────────


def list_conversation_agents(db_path: str | Path, conversation_id: str) -> list[dict[str, Any]]:
    _, _, repo = _get_repos(db_path)
    return repo.find_by_conversation(conversation_id)


# ── 消息恢复（服务启动时调用） ────────────────────────────────────


def recover_stuck_messages(db_path: str | Path) -> int:
    """恢复异常中断后卡住的消息（pending/running → failed）。

    服务重启时调用，避免前端持续显示"处理中"。
    """
    _, repo, _ = _get_repos(db_path)
    return repo.recover_stuck()


# ── 向后兼容：从 execution 模块重导出 ─────────────────────────────
# 以下符号被 routes 等模块直接引入，保持导入路径不变。

from interfaces.api.services.execution import (  # noqa: E402, F401
    _record_token_usage,
    execute_message_flow,
    list_available_agents,
)
