"""Conversation、Message、ConversationAgent 仓库 SQLite 实现。

替换 interfaces/api/services/conversations.py 中的裸 SQL 操作，
统一使用 SQLiteConnectionManager 管理连接。
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from infrastructure.persistence.connection import SQLiteConnectionManager


class ConversationRepository:
    """对话仓库 — conversations 表 CRUD。"""

    def __init__(self, conn_mgr: SQLiteConnectionManager) -> None:
        self._db = conn_mgr

    def create(self, title: str = "新对话", project_id: str = "default") -> dict[str, Any]:
        cid = uuid.uuid4().hex
        self._db.execute(
            "INSERT INTO conversations (conversation_id, project_id, title) VALUES (?, ?, ?)",
            (cid, project_id, title),
        )
        self._db.commit()
        row = self._db.execute("SELECT * FROM conversations WHERE conversation_id = ?", (cid,)).fetchone()
        return dict(row) if row else {"conversation_id": cid, "title": title}

    def find_all(
        self,
        page: int = 1,
        page_size: int = 20,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size
        if project_id:
            total = self._db.execute(
                "SELECT COUNT(*) as cnt FROM conversations WHERE project_id = ?",
                (project_id,),
            ).fetchone()["cnt"]
            rows = self._db.execute(
                """SELECT c.*, COUNT(m.message_id) as message_count
                   FROM conversations c
                   LEFT JOIN messages m ON m.conversation_id = c.conversation_id
                   WHERE c.project_id = ?
                   GROUP BY c.conversation_id
                   ORDER BY c.updated_at DESC
                   LIMIT ? OFFSET ?""",
                (project_id, page_size, offset),
            ).fetchall()
        else:
            total = self._db.execute("SELECT COUNT(*) as cnt FROM conversations").fetchone()["cnt"]
            rows = self._db.execute(
                """SELECT c.*, COUNT(m.message_id) as message_count
                   FROM conversations c
                   LEFT JOIN messages m ON m.conversation_id = c.conversation_id
                   GROUP BY c.conversation_id
                   ORDER BY c.updated_at DESC
                   LIMIT ? OFFSET ?""",
                (page_size, offset),
            ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def find_by_id(self, conversation_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,)).fetchone()
        return dict(row) if row else None

    def update(self, conversation_id: str, title: str | None = None) -> bool:
        if title:
            self._db.execute(
                "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?",
                (title, conversation_id),
            )
        else:
            self._db.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?",
                (conversation_id,),
            )
        affected = self._db.execute("SELECT changes() as cnt").fetchone()["cnt"]
        self._db.commit()
        return affected > 0

    def delete(self, conversation_id: str) -> bool:
        """删除对话及其关联的消息和 agent 跟踪记录。"""
        self._db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        self._db.execute("DELETE FROM conversation_agents WHERE conversation_id = ?", (conversation_id,))
        self._db.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
        affected = self._db.execute("SELECT changes() as cnt").fetchone()["cnt"]
        self._db.commit()
        return affected > 0

    def copy(self, conversation_id: str, new_title: str | None = None) -> dict[str, Any] | None:
        """拷贝对话及其所有消息，返回新对话。"""
        original = self._db.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
        if not original:
            return None

        new_cid = uuid.uuid4().hex
        title = new_title or (original["title"] + " (副本)")
        self._db.execute(
            "INSERT INTO conversations (conversation_id, project_id, title) VALUES (?, ?, ?)",
            (new_cid, original["project_id"], title),
        )

        rows = self._db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY sort_order, created_at",
            (conversation_id,),
        ).fetchall()
        id_map: dict[str, str] = {}
        for row in rows:
            old_id = row["message_id"]
            new_id = uuid.uuid4().hex
            id_map[old_id] = new_id
        for row in rows:
            new_id = id_map[row["message_id"]]
            new_parent = id_map.get(row["parent_id"]) if row["parent_id"] else None
            self._db.execute(
                """INSERT INTO messages
                   (message_id, conversation_id, parent_id, role, agent_name,
                    content, metadata, status, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_id,
                    new_cid,
                    new_parent,
                    row["role"],
                    row["agent_name"],
                    row["content"],
                    row["metadata"],
                    row["status"],
                    row["sort_order"],
                    row["created_at"],
                ),
            )
        self._db.commit()
        new_conv = self._db.execute("SELECT * FROM conversations WHERE conversation_id = ?", (new_cid,)).fetchone()
        return dict(new_conv) if new_conv else {"conversation_id": new_cid, "title": title}


class MessageRepository:
    """消息仓库 — messages 表 CRUD。"""

    def __init__(self, conn_mgr: SQLiteConnectionManager) -> None:
        self._db = conn_mgr

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        d = dict(row)
        if d.get("metadata"):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except Exception:
                d["metadata"] = {}
        return d

    def find_by_conversation(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY sort_order, created_at",
            (conversation_id,),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def find_by_id(self, message_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def has_running(self, conversation_id: str) -> bool:
        """检查对话是否有正在执行中的 agent 消息（pending/running）。"""
        row = self._db.execute(
            "SELECT 1 FROM messages WHERE conversation_id = ? "
            "AND role = 'agent' AND status IN ('pending', 'running') LIMIT 1",
            (conversation_id,),
        ).fetchone()
        return row is not None

    def create(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        parent_id: str | None = None,
        agent_name: str | None = None,
        status: str = "completed",
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        mid = uuid.uuid4().hex
        sort = self._db.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 as next_sort FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()["next_sort"]
        self._db.execute(
            """INSERT INTO messages
               (message_id, conversation_id, parent_id, role, agent_name,
                content, metadata, status, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mid,
                conversation_id,
                parent_id,
                role,
                agent_name,
                content,
                json.dumps(metadata or {}, ensure_ascii=False),
                status,
                sort,
            ),
        )
        self._db.commit()
        row = self._db.execute("SELECT * FROM messages WHERE message_id = ?", (mid,)).fetchone()
        return self._row_to_dict(row)

    def update_status(
        self,
        message_id: str,
        status: str,
        content: str | None = None,
        agent_name: str | None = None,
        metadata: dict | None = None,
        trace_id: str = "",
    ) -> None:
        sets = ["status = ?"]
        params: list[Any] = [status]
        if content is not None:
            sets.append("content = ?")
            params.append(content)
        if agent_name is not None:
            sets.append("agent_name = ?")
            params.append(agent_name)
        if metadata is not None:
            sets.append("metadata = ?")
            params.append(json.dumps(metadata, ensure_ascii=False))
        if trace_id:
            sets.append("trace_id = ?")
            params.append(trace_id)
        params.append(message_id)
        sql = f"UPDATE messages SET {', '.join(sets)} WHERE message_id = ?"  # noqa: S608
        self._db.execute(sql, params)
        self._db.commit()

    def delete(self, message_id: str) -> bool:
        row = self._db.execute("SELECT conversation_id FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        if not row:
            return False
        conversation_id = row["conversation_id"]
        self._db.execute("UPDATE messages SET parent_id = NULL WHERE parent_id = ?", (message_id,))
        self._db.execute("DELETE FROM messages WHERE message_id = ?", (message_id,))
        self._db.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?",
            (conversation_id,),
        )
        self._db.commit()
        return True

    def recover_stuck(self) -> int:
        """恢复异常中断后卡住的消息（pending/running → failed）。"""
        cursor = self._db.execute(
            "UPDATE messages SET status = 'failed', content = '[服务重启，消息已中断]' "
            "WHERE status IN ('pending', 'running')"
        )
        affected = cursor.rowcount
        self._db.commit()
        return affected


class ConversationAgentRepository:
    """Conversation-Agent 跟踪仓库。"""

    def __init__(self, conn_mgr: SQLiteConnectionManager) -> None:
        self._db = conn_mgr

    def ensure(self, conversation_id: str, agent_name: str) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO conversation_agents (conversation_id, agent_name) VALUES (?, ?)",
            (conversation_id, agent_name),
        )
        self._db.execute(
            "UPDATE conversation_agents SET task_count = task_count + 1 WHERE conversation_id = ? AND agent_name = ?",
            (conversation_id, agent_name),
        )
        self._db.commit()

    def find_by_conversation(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM conversation_agents WHERE conversation_id = ? ORDER BY task_count DESC",
            (conversation_id,),
        ).fetchall()
        return [dict(r) for r in rows]
