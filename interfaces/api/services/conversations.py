"""对话与消息服务。

提供 conversation/message CRUD，以及消息→agent 执行核心链路。
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from logging import getLogger
from pathlib import Path
from typing import Any

from interfaces.api.services.ws_manager import get_ws_manager

logger = getLogger("sivan.conversations")

# ── Conversation CRUD ────────────────────────────────────────────


def _get_conn(db_path: str | Path) -> sqlite3.Connection:
    """创建独立 SQLite 连接（WAL 模式）。"""
    from infrastructure.persistence.connection import _wal_connect
    return _wal_connect(db_path)


def create_conversation(db_path: str | Path, title: str = "新对话", project_id: str = "default") -> dict[str, Any]:
    conn = _get_conn(db_path)
    try:
        cid = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO conversations (conversation_id, project_id, title) VALUES (?, ?, ?)",
            (cid, project_id, title),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM conversations WHERE conversation_id = ?", (cid,)).fetchone()
        return dict(row) if row else {"conversation_id": cid, "title": title}
    finally:
        conn.close()


def list_conversations(db_path: str | Path, page: int = 1, page_size: int = 20,
                       project_id: str | None = None) -> dict[str, Any]:
    conn = _get_conn(db_path)
    try:
        conn.row_factory = sqlite3.Row
        offset = (page - 1) * page_size
        if project_id:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM conversations WHERE project_id = ?",
                (project_id,),
            ).fetchone()["cnt"]
            rows = conn.execute(
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
            total = conn.execute("SELECT COUNT(*) as cnt FROM conversations").fetchone()["cnt"]
            rows = conn.execute(
                """SELECT c.*, COUNT(m.message_id) as message_count
                   FROM conversations c
                   LEFT JOIN messages m ON m.conversation_id = c.conversation_id
                   GROUP BY c.conversation_id
                   ORDER BY c.updated_at DESC
                   LIMIT ? OFFSET ?""",
                (page_size, offset),
            ).fetchall()
        items = [dict(r) for r in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    finally:
        conn.close()


def get_conversation(db_path: str | Path, conversation_id: str) -> dict[str, Any] | None:
    conn = _get_conn(db_path)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_conversation(db_path: str | Path, conversation_id: str, title: str | None = None) -> bool:
    conn = _get_conn(db_path)
    try:
        if title:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?",
                (title, conversation_id),
            )
        else:
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?",
                (conversation_id,),
            )
        affected = conn.total_changes
        conn.commit()
        return affected > 0
    finally:
        conn.close()


def delete_conversation(db_path: str | Path, conversation_id: str) -> bool:
    import time as _time
    for attempt in range(3):
        conn = _get_conn(db_path)
        try:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversation_agents WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
            affected = conn.total_changes
            conn.commit()
            return affected > 0
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 2:
                _time.sleep(0.5 * (attempt + 1))
                continue
            raise
        finally:
            conn.close()


def copy_conversation(db_path: str | Path, conversation_id: str, new_title: str | None = None) -> dict[str, Any] | None:
    """拷贝对话及其所有消息，返回新对话。"""
    conn = _get_conn(db_path)
    try:
        conn.row_factory = sqlite3.Row
        original = conn.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
        if not original:
            return None

        new_cid = uuid.uuid4().hex
        title = new_title or (original["title"] + " (副本)")
        conn.execute(
            "INSERT INTO conversations (conversation_id, project_id, title) VALUES (?, ?, ?)",
            (new_cid, original["project_id"], title),
        )

        # 拷贝消息
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY sort_order, created_at",
            (conversation_id,),
        ).fetchall()
        # 旧 ID → 新 ID 映射（保持 parent_id 关系）
        id_map: dict[str, str] = {}
        for row in rows:
            old_id = row["message_id"]
            new_id = uuid.uuid4().hex
            id_map[old_id] = new_id
        for row in rows:
            new_id = id_map[row["message_id"]]
            new_parent = id_map.get(row["parent_id"]) if row["parent_id"] else None
            conn.execute(
                """INSERT INTO messages
                   (message_id, conversation_id, parent_id, role, agent_name, content, metadata, status, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_id, new_cid, new_parent, row["role"], row["agent_name"], row["content"],
                 row["metadata"], row["status"], row["sort_order"], row["created_at"]),
            )

        conn.commit()
        new_conv = conn.execute(
            "SELECT * FROM conversations WHERE conversation_id = ?", (new_cid,)
        ).fetchone()
        return dict(new_conv) if new_conv else {"conversation_id": new_cid, "title": title}
    finally:
        conn.close()


# ── Message CRUD ─────────────────────────────────────────────────


def _msg_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except Exception:
            d["metadata"] = {}
    return d


def list_messages(db_path: str | Path, conversation_id: str) -> list[dict[str, Any]]:
    conn = _get_conn(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY sort_order, created_at",
            (conversation_id,),
        ).fetchall()
        return [_msg_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def has_running_message(db_path: str | Path, conversation_id: str) -> bool:
    """检查对话是否有正在执行中的 agent 消息（pending/running）。"""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM messages WHERE conversation_id = ? AND role = 'agent' AND status IN ('pending', 'running') LIMIT 1",
            (conversation_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


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
    conn = _get_conn(db_path)
    try:
        conn.row_factory = sqlite3.Row
        mid = uuid.uuid4().hex
        sort = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 as next_sort FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()["next_sort"]
        conn.execute(
            """INSERT INTO messages
               (message_id, conversation_id, parent_id, role, agent_name, content, metadata, status, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mid, conversation_id, parent_id, role, agent_name, content,
             json.dumps(metadata or {}, ensure_ascii=False), status, sort),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM messages WHERE message_id = ?", (mid,)).fetchone()
        return _msg_row_to_dict(row)
    finally:
        conn.close()


def update_message_status(
    db_path: str | Path, message_id: str, status: str, content: str | None = None,
    agent_name: str | None = None, metadata: dict | None = None, trace_id: str = "",
) -> bool:
    conn = _get_conn(db_path)
    try:
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
        conn.execute(f"UPDATE messages SET {', '.join(sets)} WHERE message_id = ?", params)
        conn.commit()
        return True
    finally:
        conn.close()


def get_message(db_path: str | Path, message_id: str) -> dict[str, Any] | None:
    conn = _get_conn(db_path)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        return _msg_row_to_dict(row) if row else None
    finally:
        conn.close()


def delete_message(db_path: str | Path, message_id: str) -> bool:
    """删除单条消息。"""
    conn = _get_conn(db_path)
    try:
        row = conn.execute("SELECT conversation_id FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        if not row:
            return False
        conversation_id = row["conversation_id"]
        # 先清空引用该消息的 parent_id，避免外键约束冲突
        conn.execute("UPDATE messages SET parent_id = NULL WHERE parent_id = ?", (message_id,))
        conn.execute("DELETE FROM messages WHERE message_id = ?", (message_id,))
        # 更新对话的 updated_at
        conn.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?", (conversation_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ── Conversation-Agent tracking ──────────────────────────────────


def _ensure_conversation_agent(db_path: str | Path, conversation_id: str, agent_name: str) -> None:
    conn = _get_conn(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO conversation_agents (conversation_id, agent_name) VALUES (?, ?)",
            (conversation_id, agent_name),
        )
        conn.execute(
            "UPDATE conversation_agents SET task_count = task_count + 1 WHERE conversation_id = ? AND agent_name = ?",
            (conversation_id, agent_name),
        )
        conn.commit()
    finally:
        conn.close()


def list_conversation_agents(db_path: str | Path, conversation_id: str) -> list[dict[str, Any]]:
    conn = _get_conn(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM conversation_agents WHERE conversation_id = ? ORDER BY task_count DESC",
            (conversation_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── 消息→Agent 执行核心链路 ─────────────────────────────────────


def _parse_orchestrator_decision(result: str) -> dict:
    """解析 orchestrator 返回的 JSON 决策，非 JSON 时视为 chat 回退。"""
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "decision" in data:
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    # 非 JSON 或错误消息 → 当 chat 回退
    if result.startswith("[") or result.startswith("任务失败"):
        return {"decision": "chat", "response": f"Orchestrator 分析异常: {result[:200]}"}
    return {"decision": "chat", "response": result}


def _finalize_response(
    db_path: str | Path,
    conversation_id: str,
    message_id: str,
    content: str,
    agent_name: str,
    trace_id: str,
    ws: Any,
    db_log: Any,
) -> None:
    """结束消息执行：更新状态 + WebSocket 广播。"""
    meta = {"agent": agent_name, "trace_id": trace_id}
    update_message_status(db_path, message_id, "completed",
                          content=content, metadata=meta, trace_id=trace_id)
    _record_token_usage(db_path, agent_name, agent_name, 0, 0, content[:200])
    asyncio.run_coroutine_threadsafe(
        ws.broadcast(conversation_id, {
            "type": "status_change", "message_id": message_id,
            "status": "completed", "content": content,
            "agent_name": agent_name, "metadata": meta, "trace_id": trace_id,
        }),
        asyncio.get_running_loop(),
    )
    db_log.log("INFO", "conversation", "msg_exec_complete",
               f"msg={message_id[:8]}, agent={agent_name}", trace_id=trace_id,
               metadata={"conversation_id": conversation_id, "message_id": message_id})


async def execute_message_flow(
    db_path: str | Path,
    conversation_id: str,
    message_id: str,
    user_message_id: str,
    target_agent: str | None,
    project_id: str,
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    """后台执行消息到 agent 的完整链路。

    1. 从用户消息提取任务内容
    2. 路由（or orchestrator 路由）选定 agent
    3. 更新 agent message status=running
    4. WebSocket 推送
    5. 调用 agent.execute
    6. 更新 message status=completed/failed
    7. WebSocket 推送结果
    """
    from infrastructure.logging.db_logger import get_db_logger
    db_log = get_db_logger()

    ws = get_ws_manager()
    msg = get_message(db_path, message_id)
    user_msg = get_message(db_path, user_message_id)
    if not msg or not user_msg:
        return
    user_content = user_msg["content"]

    # 加载历史消息用于多轮对话
    # 用 sort_order 做边界过滤，防止 regenerate 时引入后续轮次的消息
    current_sort = user_msg.get("sort_order", 0)
    history = []
    try:
        all_msgs = list_messages(db_path, conversation_id)
        for m in all_msgs:
            mid = m["message_id"]
            if mid == user_message_id or mid == message_id:
                continue
            if m.get("sort_order", 0) >= current_sort:
                continue
            if m.get("status") == "completed" and m.get("content"):
                role = "user" if m["role"] == "user" else "assistant"
                history.append({"role": role, "content": m["content"]})
    except Exception:
        pass

    # 引用回复：将引用消息内容注入到当前用户消息上下文
    try:
        if user_msg:
            reply_to_id = (user_msg.get("metadata") or {}).get("reply_to_id")
            if reply_to_id:
                quoted = get_message(db_path, reply_to_id)
                if quoted and quoted.get("content"):
                    quoted_content = quoted["content"][:500]
                    quoted_role = "用户" if quoted.get("role") == "user" else "智能体"
                    quoted_name = quoted.get("agent_name") or quoted_role
                    user_content = f"【引用 {quoted_name} 的消息】\n{quoted_content}\n\n---\n{user_content}"
    except Exception:
        pass

    trace_id, _ = db_log.trace("conversation", "msg_exec_start", f"cid={conversation_id[:8]}, msg={message_id[:8]}",
                               metadata={"conversation_id": conversation_id, "message_id": message_id, "target": target_agent})

    try:
        # 1. 路由
        agent_name = target_agent
        if not agent_name:
            agent_name = _route_task(db_path, user_content, trace_id=trace_id)
        if not agent_name:
            update_message_status(db_path, message_id, "failed", content="无法路由到合适的智能体", trace_id=trace_id)
            await ws.broadcast(conversation_id, {
                "type": "status_change", "message_id": message_id,
                "status": "failed", "content": "无法路由到合适的智能体",
                "trace_id": trace_id,
            })
            return

        # 流式回调需要的 event loop（squad 和普通路径共用）
        loop = asyncio.get_running_loop()

        # 1b. Orchestrator 决策 — 路由到 orchestrator 时，进行 ReAct 三阶段分析
        if agent_name == "orchestrator" and not target_agent:
            from interfaces.api.services.squads import call_agent_for_squad
            orch_context = {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "project_id": project_id,
                "trace_id": trace_id,
                "_history": history,
            }
            try:
                orch_result = await asyncio.wait_for(
                    asyncio.to_thread(
                        call_agent_for_squad, "orchestrator", user_content, orch_context,
                    ),
                    timeout=120,
                )
            except asyncio.TimeoutError:
                orch_result = json.dumps({"decision": "chat",
                    "response": "[超时] 智能体分析超时，请稍后重试",
                    "reasoning": "orchestrator LLM 调用超时"})
            decision = _parse_orchestrator_decision(orch_result)

            # 记录 orchestrator 自身的 token 用量
            orch_input = orch_context.get("_token_input", 0)
            orch_output = orch_context.get("_token_output", 0)
            if orch_input or orch_output:
                _record_token_usage(db_path, "orchestrator", orch_context.get("_token_model", ""),
                                    orch_input, orch_output, user_content[:200])

            if decision["decision"] == "chat":
                _finalize_response(db_path, conversation_id, message_id,
                                   decision.get("response", ""), "orchestrator",
                                   trace_id, ws, db_log)
                return

            if decision["decision"] == "single":
                agent_name = decision.get("agent", "") or "orchestrator"
                refined = decision.get("refined_task", "")
                if refined:
                    user_content = refined

                # "single" 路径下 orchestrator 输出的 agent 名称是
                # LLM 生成的语义化角色名（如 "fitness_coach"），
                # 必须通过 AgentResolver 解析到真实注册表。
                if agent_name != "orchestrator":
                    from application.services.agent_resolver import AgentResolver
                    resolver = AgentResolver(db_path)
                    resolved = resolver.resolve_agent(agent_name)
                    if resolved:
                        logger.info("AgentResolver[%s]: single agent '%s' → 已注册 '%s'", trace_id[:8], agent_name, resolved)
                        agent_name = resolved
                    elif resolver._should_create_agent(agent_name):
                        new_id = resolver.create_agent(agent_name)
                        logger.info("AgentResolver[%s]: single agent '%s' → 新创建 '%s'", trace_id[:8], agent_name, new_id)
                        # 同步到全局缓存（AgentResolver 只写了自己的私有缓存）
                        from interfaces.mcp.server import get_system
                        sys_system = get_system()
                        sys_system.agent_service.reload(new_id)
                        agent_name = new_id
                    else:
                        logger.warning("AgentResolver[%s]: single agent '%s' → 不满足创建条件，保留原名称", trace_id[:8], agent_name)

            if decision["decision"] == "squad":
                topology = decision.get("topology", {})
                await _execute_dynamic_squad_flow(
                    db_path, conversation_id, message_id, user_message_id,
                    topology, user_content, trace_id, ws, cancel_check, loop,
                )
                return

        # 2. 更新 running
        update_message_status(db_path, message_id, "running", agent_name=agent_name, trace_id=trace_id)
        _ensure_conversation_agent(db_path, conversation_id, agent_name)
        await ws.broadcast(conversation_id, {
            "type": "status_change", "message_id": message_id,
            "status": "running", "agent_name": agent_name,
            "trace_id": trace_id,
        })
        update_conversation(db_path, conversation_id)

        # 3. 执行
        from interfaces.api.services.squads import call_agent_for_squad
        start = time.time()

        def stream_callback(chunk: str) -> None:
            if cancel_check and cancel_check():
                return
            asyncio.run_coroutine_threadsafe(
                ws.broadcast(conversation_id, {
                    "type": "message_chunk",
                    "message_id": message_id,
                    "agent_name": agent_name,
                    "content": chunk,
                    "trace_id": trace_id,
                }),
                loop,
            )

        def reasoning_callback(chunk: str) -> None:
            if cancel_check and cancel_check():
                return
            asyncio.run_coroutine_threadsafe(
                ws.broadcast(conversation_id, {
                    "type": "reasoning_chunk",
                    "message_id": message_id,
                    "agent_name": agent_name,
                    "content": chunk,
                    "trace_id": trace_id,
                }),
                loop,
            )

        context = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "project_id": project_id,
            "trace_id": trace_id,
            "_history": history,
            "_stream_callback": stream_callback,
            "_reasoning_callback": reasoning_callback,
        }
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    call_agent_for_squad, agent_name, user_content, context,
                ),
                timeout=300,
            )
        except asyncio.TimeoutError:
            result = f"[错误] 执行超时"
        except Exception as exc:
            result = f"[错误] {exc}"

        # 检查是否已被用户取消
        if cancel_check and cancel_check():
            update_message_status(db_path, message_id, "cancelled", trace_id=trace_id)
            await ws.broadcast(conversation_id, {
                "type": "status_change", "message_id": message_id,
                "status": "cancelled", "content": "用户已取消",
                "trace_id": trace_id,
            })
            db_log.log("INFO", "conversation", "msg_exec_cancelled",
                       f"msg={message_id[:8]}, agent={agent_name}", trace_id=trace_id,
                       metadata={"conversation_id": conversation_id, "message_id": message_id})
            return

        elapsed_ms = int((time.time() - start) * 1000)
        token_used = context.get("_token_used", 0)
        token_input = context.get("_token_input", 0)
        token_output = context.get("_token_output", 0)
        token_model = context.get("_token_model", "")
        reasoning = context.get("_reasoning_content", "")
        meta = {"elapsed_ms": elapsed_ms, "agent": agent_name, "token_used": token_used,
                 "token_input": token_input, "token_output": token_output, "model": token_model,
                 "trace_id": trace_id}
        if reasoning:
            meta["reasoning"] = reasoning
        content_str = str(result)
        status = "completed" if not content_str.startswith("[错误]") and not content_str.startswith("任务失败:") else "failed"
        update_message_status(db_path, message_id, status, content=content_str, metadata=meta, trace_id=trace_id)

        # 5. 记录 Token 使用到统计表
        _record_token_usage(db_path, agent_name, token_model or agent_name,
                            token_input, token_output, user_content[:200])

        # 4. WebSocket 推送
        await ws.broadcast(conversation_id, {
            "type": "status_change", "message_id": message_id,
            "status": status, "content": result, "agent_name": agent_name,
            "metadata": meta, "trace_id": trace_id,
        })

        db_log.log("INFO", "conversation", "msg_exec_complete",
                   f"msg={message_id[:8]}, agent={agent_name}, status={status}",
                   trace_id=trace_id, duration_ms=elapsed_ms,
                   metadata={"conversation_id": conversation_id, "message_id": message_id, "agent": agent_name, "status": status})
    except Exception as _exc:
        import traceback
        _tb = traceback.format_exc()
        db_log.log("ERROR", "conversation", "msg_exec_crash",
                   f"msg={message_id[:8]} crashed: {_tb}",
                   trace_id=trace_id,
                   metadata={"conversation_id": conversation_id, "message_id": message_id})
        _err_msg = f"执行异常: {type(_exc).__name__}: {_exc}"
        try:
            update_message_status(db_path, message_id, "failed", content=_err_msg, trace_id=trace_id)
            await ws.broadcast(conversation_id, {
                "type": "status_change", "message_id": message_id,
                "status": "failed", "content": _err_msg,
                "trace_id": trace_id,
            })
        except Exception:
            pass


async def _execute_squad_flow(
    db_path: str | Path,
    conversation_id: str,
    message_id: str,
    user_message_id: str,
    squad_match: Any,  # SquadMatch
    routed_agent: str,
    trace_id: str,
    ws: Any,
    cancel_check: Any,
    loop: Any,
) -> None:
    """执行 Squad 流（HITL 模式），第一阶段执行后暂停等待用户操作。"""
    from interfaces.api.services.squads import execute_squad_hitl
    from infrastructure.logging.db_logger import get_db_logger
    db_log = get_db_logger()

    squad_id = squad_match.squad_id

    # 重新读取用户消息内容
    user_msg = get_message(db_path, user_message_id)
    user_content = user_msg.get("content", "") if user_msg else ""

    # 创建流式回调
    def stream_callback(chunk: str) -> None:
        if cancel_check and cancel_check():
            return
        asyncio.run_coroutine_threadsafe(
            ws.broadcast(conversation_id, {
                "type": "message_chunk",
                "message_id": message_id,
                "agent_name": squad_match.squad_name,
                "content": chunk,
                "trace_id": trace_id,
            }),
            loop,
        )

    _reasoning_accumulator: list[str] = []

    def reasoning_callback(chunk: str) -> None:
        if cancel_check and cancel_check():
            return
        _reasoning_accumulator.append(chunk)
        asyncio.run_coroutine_threadsafe(
            ws.broadcast(conversation_id, {
                "type": "reasoning_chunk",
                "message_id": message_id,
                "agent_name": squad_match.squad_name,
                "content": chunk,
                "trace_id": trace_id,
            }),
            loop,
        )

    # 更新状态为 running（squad 模式）
    meta = {"squad_id": squad_id, "squad_name": squad_match.squad_name, "agent": routed_agent, "trace_id": trace_id}
    update_message_status(db_path, message_id, "running", agent_name=squad_match.squad_name, metadata=meta, trace_id=trace_id)
    _ensure_conversation_agent(db_path, conversation_id, squad_match.squad_name)
    await ws.broadcast(conversation_id, {
        "type": "status_change", "message_id": message_id,
        "status": "running", "agent_name": squad_match.squad_name,
        "metadata": meta, "trace_id": trace_id,
    })
    update_conversation(db_path, conversation_id)

    # Squad 阶段开始提示
    await ws.broadcast(conversation_id, {
        "type": "squad_phase_start", "message_id": message_id,
        "phase": 0, "phase_name": "前置检查",
        "agents": [], "trace_id": trace_id,
    })

    try:
        # 执行第一阶段（HITL 模式）
        import time as _time
        start = _time.time()
        extra_ctx = {
            "_stream_callback": stream_callback,
            "_reasoning_callback": reasoning_callback,
            "_squad_execution": True,
            "trace_id": trace_id,
        }
        result = await asyncio.to_thread(
            execute_squad_hitl, str(db_path), squad_id,
            {"description": f"Squad: {squad_match.squad_name}", "trigger_type": "conversation",
             "created_by": "user", "input_params": {"task": user_content}},
            extra_context=extra_ctx,
        )

        if not result.get("success"):
            raise Exception(result.get("error", "Squad 执行启动失败"))

        # 记录首个 phase 的 token 用量
        _record_token_usage(
            db_path, squad_match.squad_name,
            result.get("token_model", ""),
            result.get("token_input", 0),
            result.get("token_output", 0),
            user_content[:200],
        )

        execution_id = result["execution_id"]
        elapsed_ms = int((_time.time() - start) * 1000)
        hitl_waiting = result.get("hitl_waiting", True)

        # 存储 execution_id 到 metadata
        squad_meta = {
            "squad_id": squad_id,
            "squad_name": squad_match.squad_name,
            "execution_id": execution_id,
            "hitl_waiting": hitl_waiting,
            "current_phase": result.get("current_phase", 1),
            "current_phase_name": result.get("current_phase_name", ""),
            "total_phases": result.get("total_phases", 0),
            "phase_status": result.get("phase_status", ""),
            "elapsed_ms": elapsed_ms,
            "trace_id": trace_id,
            "reasoning": "".join(_reasoning_accumulator),
        }
        phase_output = result.get("current_phase_output", {})

        # 推第一阶段结果
        await ws.broadcast(conversation_id, {
            "type": "squad_phase_result", "message_id": message_id,
            "execution_id": execution_id,
            "phase": result.get("current_phase", 1),
            "phase_name": result.get("current_phase_name", ""),
            "results": phase_output,
            "trace_id": trace_id,
        })

        if hitl_waiting:
            # 推 HITL 暂停（等待用户操作）
            await ws.broadcast(conversation_id, {
                "type": "squad_hitl_pause", "message_id": message_id,
                "execution_id": execution_id,
                "phase": result.get("current_phase", 1),
                "phase_name": result.get("current_phase_name", ""),
                "phase_output": phase_output,
                "total_phases": result.get("total_phases", 0),
                "trace_id": trace_id,
            })

            # 更新 message 为 hitl_waiting 状态
            update_message_status(db_path, message_id, "running", metadata=squad_meta, trace_id=trace_id)
            await ws.broadcast(conversation_id, {
                "type": "status_change", "message_id": message_id,
                "status": "running", "agent_name": squad_match.squad_name,
                "metadata": squad_meta, "trace_id": trace_id,
            })
        else:
            # Squad 一次性完成（如单阶段 squad），标记消息为 completed
            squad_meta["squad_complete"] = True
            # 拼接阶段产出
            phase_outputs = result.get("current_phase_output", {})
            content_parts = []
            if isinstance(phase_outputs, dict):
                for agent_name, text in phase_outputs.items():
                    if text:
                        content_parts.append(f"### {agent_name}\n\n{text}")
            completed_content = "\n\n---\n\n".join(content_parts) if content_parts else f"Squad 执行完成（共 {result.get('total_phases', 0)} 阶段）"
            squad_meta["elapsed_ms"] = result.get("elapsed_ms", elapsed_ms)
            update_message_status(db_path, message_id, "completed", content=completed_content,
                                  metadata=squad_meta, trace_id=trace_id)
            await ws.broadcast(conversation_id, {
                "type": "status_change", "message_id": message_id,
                "status": "completed", "agent_name": squad_match.squad_name,
                "content": completed_content, "metadata": squad_meta, "trace_id": trace_id,
            })
            await ws.broadcast(conversation_id, {
                "type": "squad_complete", "message_id": message_id,
                "status": "completed", "execution_id": execution_id,
                "total_phases": result.get("total_phases", 0),
            })

        db_log.log("INFO", "squad", "hitl_flow_first_phase_done",
                   f"msg={message_id[:8]}, squad={squad_id}, exec={execution_id}",
                   trace_id=trace_id, duration_ms=elapsed_ms,
                   metadata={"conversation_id": conversation_id, "message_id": message_id,
                             "execution_id": execution_id, "squad_id": squad_id})

    except Exception as exc:
        import traceback as _tb
        _tb_str = _tb.format_exc()
        db_log.log("ERROR", "squad", "hitl_flow_failed",
                   f"msg={message_id[:8]} squad={squad_id}: {exc}",
                   trace_id=trace_id,
                   metadata={"conversation_id": conversation_id, "message_id": message_id,
                             "squad_id": squad_id, "error": str(exc)[:500]})
        err_msg = f"Squad 执行失败: {exc}"
        update_message_status(db_path, message_id, "failed", content=err_msg, trace_id=trace_id)
        await ws.broadcast(conversation_id, {
            "type": "status_change", "message_id": message_id,
            "status": "failed", "content": err_msg,
            "trace_id": trace_id,
        })


# ── Squad 路由决策记录 ────────────────────────────────────────────


async def _execute_dynamic_squad_flow(
    db_path: str | Path,
    conversation_id: str,
    message_id: str,
    user_message_id: str,
    topology: dict[str, Any],
    user_content: str,
    trace_id: str,
    ws: Any,
    cancel_check: Any,
    loop: Any,
) -> None:
    """执行动态编排（由 Orchestrator 生成拓扑），流式推送结果到对话。"""
    from interfaces.api.services.squads import execute_dynamic_squad
    from infrastructure.logging.db_logger import get_db_logger
    db_log = get_db_logger()

    phases = topology.get("phases", [])
    mode = topology.get("mode", "sequential")

    squad_name = f"动态编排 ({mode})"
    meta = {"topology_mode": mode, "phase_count": len(phases), "dynamic_squad": True, "trace_id": trace_id}
    update_message_status(db_path, message_id, "running", agent_name=squad_name, metadata=meta, trace_id=trace_id)
    await ws.broadcast(conversation_id, {
        "type": "status_change", "message_id": message_id,
        "status": "running", "agent_name": squad_name,
        "metadata": meta, "trace_id": trace_id,
    })
    update_conversation(db_path, conversation_id)

    _reasoning_accumulator: list[str] = []

    def stream_callback(chunk: str) -> None:
        if cancel_check and cancel_check():
            return
        asyncio.run_coroutine_threadsafe(
            ws.broadcast(conversation_id, {
                "type": "message_chunk",
                "message_id": message_id,
                "agent_name": squad_name,
                "content": chunk,
                "trace_id": trace_id,
            }),
            loop,
        )

    def reasoning_callback(chunk: str) -> None:
        if cancel_check and cancel_check():
            return
        _reasoning_accumulator.append(chunk)
        asyncio.run_coroutine_threadsafe(
            ws.broadcast(conversation_id, {
                "type": "reasoning_chunk",
                "message_id": message_id,
                "agent_name": squad_name,
                "content": chunk,
                "trace_id": trace_id,
            }),
            loop,
        )

    extra_context = {
        "_stream_callback": stream_callback,
        "_reasoning_callback": reasoning_callback,
        "trace_id": trace_id,
    }

    try:
        result = await asyncio.to_thread(
            execute_dynamic_squad, str(db_path), topology, user_content, extra_context,
        )

        content_parts = []
        for p in phases:
            pn = p.get("phase", "?")
            pd = p.get("description", f"阶段 {pn}")
            agents = p.get("agents", [])
            content_parts.append(f"**{pd}**（{', '.join(agents) if agents else '无智能体'}）")
        if result.get("success"):
            summary = "动态编排执行完成\n\n" + "\n\n".join(content_parts)
        else:
            summary = f"动态编排执行异常: {result.get('status', 'unknown')}\n\n" + "\n\n".join(content_parts)

        phase_count = len(phases)
        final_meta = {
            "topology_mode": mode, "phase_count": phase_count,
            "dynamic_squad": True, "trace_id": trace_id,
            "reasoning": "".join(_reasoning_accumulator),
        }
        final_status = "completed" if result.get("success") else "failed"
        update_message_status(db_path, message_id, final_status, content=summary,
                              metadata=final_meta, trace_id=trace_id)
        await ws.broadcast(conversation_id, {
            "type": "status_change", "message_id": message_id,
            "status": final_status, "content": summary,
            "agent_name": squad_name, "metadata": final_meta, "trace_id": trace_id,
        })

        db_log.log("INFO", "conversation", "dynamic_squad_complete",
                   f"msg={message_id[:8]}, phases={phase_count}",
                   trace_id=trace_id,
                   metadata={"conversation_id": conversation_id, "message_id": message_id,
                             "topology_mode": mode, "phase_count": phase_count})

    except Exception as exc:
        import traceback as _tb
        _tb_str = _tb.format_exc()
        db_log.log("ERROR", "conversation", "dynamic_squad_failed",
                   f"msg={message_id[:8]}: {exc}",
                   trace_id=trace_id,
                   metadata={"conversation_id": conversation_id, "message_id": message_id,
                             "error": str(exc)[:500]})
        err_msg = f"动态编排执行失败: {exc}"
        update_message_status(db_path, message_id, "failed", content=err_msg, trace_id=trace_id)
        await ws.broadcast(conversation_id, {
            "type": "status_change", "message_id": message_id,
            "status": "failed", "content": err_msg,
            "trace_id": trace_id,
        })


def _record_squad_routing_decision(
    db_path: str | Path, task_description: str, squad_match: Any,
    routed_agent: str, trace_id: str = "", start_time: float | None = None,
) -> None:
    """将 squad 匹配结果记录为路由决策，供路由分析页面展示。"""
    import time as time_module

    conn = _get_conn(db_path)
    try:
        elapsed_ms = int((time_module.time() - (start_time or time_module.time())) * 1000)
        context = {
            "squad_id": squad_match.squad_id,
            "match_reason": squad_match.match_reason,
            "routed_agent": routed_agent,
            "workflow_type": squad_match.workflow_type,
            "phase_count": squad_match.phase_count,
        }
        cursor = conn.execute(
            "INSERT INTO routing_decisions (decision_id, task_description, selected_agent, routing_strategy, "
            "confidence_score, execution_time_ms, status, context_json, created_at) "
            "VALUES (?, ?, ?, 'squad', ?, ?, 'success', ?, CURRENT_TIMESTAMP)",
            (
                trace_id or squad_match.squad_id,
                task_description[:500],
                f"[Squad] {squad_match.squad_name}",
                squad_match.confidence,
                elapsed_ms,
                json.dumps(context, ensure_ascii=False),
            ),
        )
        decision_pk = cursor.lastrowid
        # 记录候选得分：match_reason 中的各个匹配维度
        candidates = [
            ("路由智能体匹配", 3, 1),
            ("关键词匹配", 2, 2),
            ("阶段名称匹配", 1, 3),
        ]
        for cname, cscore, crank in candidates:
            conn.execute(
                "INSERT INTO candidate_scores (decision_id, agent_name, score, rank) VALUES (?, ?, ?, ?)",
                (decision_pk, cname, cscore / 6.0, crank),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _route_task(db_path: str | Path, content: str, trace_id: str = "") -> str:
    """路由任务到最合适的智能体，无匹配时由 orchestrator 托底处理。"""
    try:
        from interfaces.mcp.server import get_system
        system = get_system()
        if system and hasattr(system, "routing_service"):
            context = {"db_path": str(db_path), "source": "conversation"}
            if trace_id:
                context["trace_id"] = trace_id
            best_agent = system.routing_service.route(content, context)
            if best_agent:
                return best_agent
    except Exception:
        pass
    return "orchestrator"


def _record_token_usage(
    db_path: str | Path, agent_name: str, model: str,
    input_tokens: int, output_tokens: int, task_description: str = "",
) -> None:
    """记录 token 使用到 token_usage 统计表。"""
    conn = _get_conn(db_path)
    try:
        total = input_tokens + output_tokens
        # 简化计价：1M tokens ≈ $2（按默认价格）
        cost = (total / 1_000_000) * 2.0
        conn.execute(
            """INSERT INTO token_usage
               (agent_name, model, input_tokens, output_tokens, total_tokens, cost_usd, task_description, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (agent_name, model, input_tokens, output_tokens, total, round(cost, 6), task_description),
        )
        conn.commit()
    except Exception as exc:
        logger.warning("记录 token 用量失败: %s", exc)
    finally:
        conn.close()


def recover_stuck_messages(db_path: str | Path) -> int:
    """恢复异常中断后卡住的消息（pending/running → failed）。

    服务重启时调用，避免前端持续显示"处理中"。
    返回恢复的消息数。
    """
    conn = _get_conn(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET status = 'failed', content = '[服务重启，消息已中断]' "
            "WHERE status IN ('pending', 'running')"
        )
        affected = cursor.rowcount
        conn.commit()
        return affected
    except Exception:
        return 0
    finally:
        conn.close()


def list_available_agents() -> list[dict[str, Any]]:
    """列出所有可用 agent 供前端 @mention 用。"""
    try:
        from interfaces.mcp.server import get_system
        system = get_system()
        if system and hasattr(system, "agent_service"):
            return system.agent_service.list_agents()
    except Exception:
        pass
    return []
