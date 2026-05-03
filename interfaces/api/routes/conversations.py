"""对话与消息路由 (API + WebSocket + 页面)。"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services.conversations import (
    _record_token_usage,
    copy_conversation,
    create_conversation,
    create_message,
    delete_conversation,
    execute_message_flow,
    get_conversation,
    get_message,
    list_available_agents,
    list_conversations,
    list_messages,
    update_conversation,
    update_message_status,
)
from interfaces.api.services.ws_manager import get_ws_manager

router = APIRouter(tags=["conversations"])

# 运行中的消息取消跟踪（message_id → 时间戳），5 分钟 TTL 自动清理
_cancelled_messages: dict[str, float] = {}
_CANCEL_TTL = 300  # 5 分钟


def _is_cancelled(mid: str) -> bool:
    """检查消息是否被取消，同时清理过期条目。"""
    now = time.time()
    expired = [k for k, ts in _cancelled_messages.items() if now - ts > _CANCEL_TTL]
    for k in expired:
        _cancelled_messages.pop(k, None)
    return mid in _cancelled_messages


# ── 页面 ─────────────────────────────────────────────────────────


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    ctx: AppContext = request.app.state.context
    template = ctx.jinja_env.get_template("chat.html")
    return HTMLResponse(content=template.render(request=request))


# ── Conversation CRUD ────────────────────────────────────────────


@router.get("/api/conversations")
async def api_list_conversations(request: Request, page: int = Query(1), page_size: int = Query(20),
                                 project_id: str | None = Query(None)):
    ctx: AppContext = request.app.state.context
    return list_conversations(ctx.db_path, page=page, page_size=page_size, project_id=project_id)


@router.post("/api/conversations")
async def api_create_conversation(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    conv = create_conversation(ctx.db_path, title=body.get("title", "新对话"),
                               project_id=body.get("project_id", "default"))
    return conv


@router.get("/api/conversations/{conversation_id}")
async def api_get_conversation(request: Request, conversation_id: str):
    ctx: AppContext = request.app.state.context
    conv = get_conversation(ctx.db_path, conversation_id)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})
    return conv


@router.put("/api/conversations/{conversation_id}")
async def api_update_conversation(request: Request, conversation_id: str):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    update_conversation(ctx.db_path, conversation_id, title=body.get("title"))
    return {"success": True}


@router.delete("/api/conversations/{conversation_id}")
async def api_delete_conversation(request: Request, conversation_id: str):
    ctx: AppContext = request.app.state.context
    ok = delete_conversation(ctx.db_path, conversation_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})
    return {"success": True}


@router.post("/api/conversations/{conversation_id}/duplicate")
async def api_duplicate_conversation(request: Request, conversation_id: str):
    """拷贝对话（含消息）。"""
    ctx: AppContext = request.app.state.context
    body = await request.json() if request.headers.get("content-type") else {}
    new_title = body.get("title") if isinstance(body, dict) else None
    conv = copy_conversation(ctx.db_path, conversation_id, new_title=new_title)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})
    return conv


# ── Message ──────────────────────────────────────────────────────


@router.get("/api/conversations/{conversation_id}/messages")
async def api_list_messages(request: Request, conversation_id: str):
    ctx: AppContext = request.app.state.context
    return list_messages(ctx.db_path, conversation_id)


@router.post("/api/conversations/{conversation_id}/messages")
async def api_send_message(request: Request, conversation_id: str):
    """发送消息并触发 agent 后台执行。

    请求体:
      content (str)       — 消息内容
      target_agent (str)  — 可选，指定 agent
      project_id (str)    — 可选，项目 ID

    返回 message_id，前端通过 WebSocket 接收执行进度推送。
    """
    ctx: AppContext = request.app.state.context
    body = await request.json()
    content = body.get("content", "").strip()
    if not content:
        return JSONResponse(status_code=400, content={"error": "消息不能为空"})

    conv = get_conversation(ctx.db_path, conversation_id)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})

    # 检查是否有正在执行的消息
    from interfaces.api.services.conversations import has_running_message
    if has_running_message(ctx.db_path, conversation_id):
        return JSONResponse(status_code=409, content={"error": "当前对话有消息正在执行中，请等待完成后再发送"})

    # 检测 @agent 语法
    target_agent = body.get("target_agent", "") or None
    reply_to_id = body.get("reply_to_id", "") or None
    if not target_agent and content.startswith("@"):
        parts = content.split(" ", 1)
        target_agent = parts[0][1:].strip()
        content = parts[1] if len(parts) > 1 else ""
        if not content:
            return JSONResponse(status_code=400, content={"error": "请在 @agent 后输入消息"})

    # 存储用户消息
    user_meta = {}
    if reply_to_id:
        user_meta["reply_to_id"] = reply_to_id
    user_msg = create_message(ctx.db_path, conversation_id, "user", content, metadata=user_meta)

    # 存储 agent 占位（status=pending），触发后台执行
    agent_msg = create_message(
        ctx.db_path, conversation_id, "agent", "",
        parent_id=user_msg["message_id"], status="pending",
        metadata={"target_agent": target_agent or "auto"},
    )

    # 后台执行
    project_id = body.get("project_id", conv.get("project_id", "default"))
    _cancelled_messages.pop(agent_msg["message_id"], None)
    cancel_check = lambda mid=agent_msg["message_id"]: _is_cancelled(mid)
    asyncio.create_task(
        execute_message_flow(ctx.db_path, conversation_id, agent_msg["message_id"], user_msg["message_id"], target_agent, project_id, cancel_check=cancel_check)
    )

    return {
        "message_id": agent_msg["message_id"],
        "user_message_id": user_msg["message_id"],
        "status": "pending",
    }


@router.post("/api/conversations/{conversation_id}/messages/{message_id}/cancel")
async def api_cancel_message(request: Request, conversation_id: str, message_id: str):
    """取消正在执行的 agent 消息。"""
    ctx: AppContext = request.app.state.context
    _cancelled_messages[message_id] = time.time()
    from interfaces.api.services.conversations import update_message_status, get_message
    update_message_status(ctx.db_path, message_id, "cancelled", content="用户已取消")
    # 广播 WebSocket 通知前端更新状态
    msg = get_message(ctx.db_path, message_id)
    ws = get_ws_manager()
    await ws.broadcast(conversation_id, {
        "type": "status_change",
        "message_id": message_id,
        "agent_name": (msg.get("agent_name") or "") if msg else "",
        "content": "用户已取消",
        "status": "cancelled",
        "metadata": (msg.get("metadata") or {}) if msg else {},
    })
    return {"status": "cancelled"}


@router.post("/api/conversations/{conversation_id}/messages/{message_id}/regenerate")
async def api_regenerate_message(request: Request, conversation_id: str, message_id: str):
    """重新生成 agent 回复 — 重置消息为 pending 并重新执行。"""
    ctx: AppContext = request.app.state.context

    from interfaces.api.services.conversations import has_running_message
    if has_running_message(ctx.db_path, conversation_id):
        return JSONResponse(status_code=409, content={"error": "当前对话有消息正在执行中"})

    msg = get_message(ctx.db_path, message_id)
    if not msg or msg["role"] != "agent":
        return JSONResponse(status_code=404, content={"error": "消息不存在或不是 agent 消息"})

    user_message_id = msg.get("parent_id")
    if not user_message_id:
        return JSONResponse(status_code=400, content={"error": "无法找到对应的用户消息"})

    user_msg = get_message(ctx.db_path, user_message_id)
    if not user_msg or user_msg["role"] != "user":
        return JSONResponse(status_code=400, content={"error": "父消息不是用户消息"})

    conv = get_conversation(ctx.db_path, conversation_id)
    if not conv:
        return JSONResponse(status_code=404, content={"error": "对话不存在"})

    # 重置 agent 消息为 pending，清空内容和 metadata
    update_message_status(ctx.db_path, message_id, "pending", content="", metadata={})

    # 广播重置状态到前端
    ws = get_ws_manager()
    await ws.broadcast(conversation_id, {
        "type": "status_change",
        "message_id": message_id,
        "status": "pending",
        "agent_name": "",
        "content": "",
        "metadata": {},
    })

    # 重新执行消息流
    target_agent = (msg.get("metadata") or {}).get("target_agent", None) or None
    project_id = conv.get("project_id", "default")
    _cancelled_messages.pop(message_id, None)
    cancel_check = lambda mid=message_id: _is_cancelled(mid)
    asyncio.create_task(
        execute_message_flow(
            ctx.db_path, conversation_id, message_id, user_message_id,
            target_agent, project_id, cancel_check=cancel_check,
        )
    )

    return {"status": "pending"}


@router.delete("/api/conversations/{conversation_id}/messages/{message_id}")
async def api_delete_message(request: Request, conversation_id: str, message_id: str):
    """删除单条消息。"""
    ctx: AppContext = request.app.state.context
    from interfaces.api.services.conversations import delete_message as svc_delete
    ok = svc_delete(ctx.db_path, message_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "消息不存在"})
    return {"success": True}


@router.put("/api/conversations/{conversation_id}/messages/{message_id}/feedback")
async def api_message_feedback(request: Request, conversation_id: str, message_id: str):
    """消息评价（有用/无用）。"""
    ctx: AppContext = request.app.state.context
    body = await request.json()
    rating = body.get("rating", "")
    if rating not in ("like", "dislike", ""):
        # emoji 评价
        if rating and len(rating) > 10:
            return JSONResponse(status_code=400, content={"error": "rating 过长"})

    msg = get_message(ctx.db_path, message_id)
    if not msg:
        return JSONResponse(status_code=404, content={"error": "消息不存在"})
    meta = dict(msg.get("metadata", {}) or {})
    meta["user_rating"] = rating
    update_message_status(ctx.db_path, message_id, status=msg.get("status", "completed"), metadata=meta)
    return {"success": True}


@router.post("/api/conversations/{conversation_id}/messages/{message_id}/save-to-kb")
async def api_save_message_to_kb(request: Request, conversation_id: str, message_id: str):
    """将消息内容保存到知识库。"""
    ctx: AppContext = request.app.state.context
    msg = get_message(ctx.db_path, message_id)
    if not msg:
        return JSONResponse(status_code=404, content={"error": "消息不存在"})
    # 接收前端传入参数
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    content_type = body.get("content_type", "response")
    if content_type == "reasoning":
        content = ((msg.get("metadata") or {}).get("reasoning") or "").strip()
    else:
        content = (msg.get("content") or "").strip()
    if not content:
        return JSONResponse(status_code=400, content={"error": "消息内容为空"})

    kb_name = (body.get("kb_name") or "").strip() or "默认知识库"
    title = (body.get("title") or "").strip() or "对话记录"

    from interfaces.api.services.knowledge_base import kb_service_for_context

    svc = kb_service_for_context(ctx)

    # 自动创建知识库（如不存在）
    exists = svc.get_knowledge_base(kb_name)
    if not exists:
        svc.create_knowledge_base(kb_name, f"从对话 {conversation_id[:8]} 自动创建")

    # 导入内容
    result = svc.ingest_text(kb_name, content, filename=f"{title}.md")
    return JSONResponse({
        "success": True,
        "kb_name": kb_name,
        "title": title,
        "doc_id": result.get("doc_id"),
    })


@router.post("/api/conversations/{conversation_id}/squad-advance")
async def api_squad_advance(request: Request, conversation_id: str):
    """推进 HITL Squad 执行：继续 / 修正后继续 / 中止。

    请求体:
      message_id     : str  — 对应 agent message
      action         : str  — "continue" / "correct" / "abort"
      correction_text: str  — 修正内容（action=correct 时必需）
    """
    ctx: AppContext = request.app.state.context
    body = await request.json()
    message_id = body.get("message_id", "")
    action = body.get("action", "continue")
    correction_text = body.get("correction_text")

    if not message_id:
        return JSONResponse(status_code=400, content={"error": "message_id 不能为空"})

    # 从 message metadata 读取 execution_id
    msg = get_message(ctx.db_path, message_id)
    if not msg:
        return JSONResponse(status_code=404, content={"error": "消息不存在"})
    meta = msg.get("metadata", {}) or {}
    execution_id = meta.get("execution_id", "")
    conv_id = msg.get("conversation_id", "")

    if not execution_id:
        return JSONResponse(status_code=400, content={"error": "消息关联的 Squad 执行不存在"})

    from interfaces.api.services.squads import advance_squad_execution
    from interfaces.api.services.ws_manager import get_ws_manager as get_ws
    ws = get_ws()

    # 创建流式回调（advance 阶段也能流式推送）
    loop = asyncio.get_running_loop()

    _reasoning_accumulator: list[str] = []
    existing_reasoning = meta.get("reasoning", "")
    if existing_reasoning:
        _reasoning_accumulator.append(existing_reasoning)

    def stream_callback(chunk: str) -> None:
        asyncio.run_coroutine_threadsafe(
            ws.broadcast(conv_id, {
                "type": "message_chunk",
                "message_id": message_id,
                "agent_name": meta.get("squad_name", "Squad"),
                "content": chunk,
            }),
            loop,
        )

    def reasoning_callback(chunk: str) -> None:
        _reasoning_accumulator.append(chunk)
        asyncio.run_coroutine_threadsafe(
            ws.broadcast(conv_id, {
                "type": "reasoning_chunk",
                "message_id": message_id,
                "agent_name": meta.get("squad_name", "Squad"),
                "content": chunk,
            }),
            loop,
        )

    extra_ctx = {
        "_stream_callback": stream_callback,
        "_reasoning_callback": reasoning_callback,
        "_squad_execution": True,
    }

    # 立即标记为非 HITL 等待态，防止执行过程中刷新页面误恢复 HITL 模式
    if action in ("continue", "correct"):
        run_meta = {**meta, "hitl_waiting": False}
        from interfaces.api.services.conversations import update_message_status as _ums
        _ums(ctx.db_path, message_id, "running", metadata=run_meta)
        await ws.broadcast(conv_id, {
            "type": "status_change", "message_id": message_id,
            "status": "running",
            "agent_name": run_meta.get("squad_name", "Squad"),
            "metadata": run_meta,
        })

    result = await asyncio.to_thread(
        advance_squad_execution,
        ctx.db_path, execution_id, action, correction_text,
        extra_context=extra_ctx,
    )

    if not result.get("success"):
        return JSONResponse(status_code=400, content=result)

    # 推送到 WebSocket
    reasoning_text = "".join(_reasoning_accumulator)

    if result.get("status") == "aborted":
        update_message_status(ctx.db_path, message_id, "cancelled", content="Squad 执行已中止",
                              metadata={**meta, "hitl_waiting": False, "reasoning": reasoning_text})
        await ws.broadcast(conv_id, {
            "type": "status_change", "message_id": message_id,
            "status": "cancelled", "content": "Squad 执行已中止",
            "metadata": {**meta, "hitl_waiting": False, "reasoning": reasoning_text},
        })
        await ws.broadcast(conv_id, {
            "type": "squad_complete", "message_id": message_id,
            "status": "aborted", "execution_id": execution_id,
        })
        return {"status": "aborted"}

    if result.get("hitl_complete"):
        # 全部阶段完成 — 拼接各阶段智能体产出
        all_outputs = result.get("all_phase_outputs", {})
        content_parts = []
        for phase_key in sorted(all_outputs.keys()):
            outputs = all_outputs[phase_key]
            if isinstance(outputs, dict):
                for agent_name, text in outputs.items():
                    if text:
                        content_parts.append(f"### {agent_name}\n\n{text}")
        full_content = "\n\n---\n\n".join(content_parts) if content_parts else f"Squad 执行完成（共 {result.get('total_phases')} 阶段）"

        # 元数据：token + 耗时
        token_model = result.get("token_model", "")
        token_input = result.get("token_input", 0)
        token_output = result.get("token_output", 0)
        msg_meta = {
            **meta,
            "hitl_waiting": False,
            "squad_complete": True,
            "reasoning": reasoning_text,
            "elapsed_ms": result.get("elapsed_ms", 0),
            "token_used": result.get("token_used", 0),
            "token_input": token_input,
            "token_output": token_output,
        }
        if token_model:
            msg_meta["token_model"] = token_model

        # 记录本次 advance 阶段的 token 用量
        _record_token_usage(
            ctx.db_path, meta.get("squad_name", "Squad"),
            token_model, token_input, token_output,
        )

        update_message_status(ctx.db_path, message_id, "completed", content=full_content,
                              metadata=msg_meta)
        await ws.broadcast(conv_id, {
            "type": "status_change", "message_id": message_id,
            "status": "completed", "agent_name": meta.get("squad_name", "Squad"),
            "content": full_content, "metadata": msg_meta,
        })
        await ws.broadcast(conv_id, {
            "type": "squad_complete", "message_id": message_id,
            "status": "completed", "execution_id": execution_id,
            "total_phases": result.get("total_phases", 0),
        })
        return {"status": "completed"}

    # 中间阶段：推送下一阶段结果 + HITL 暂停
    phase_output = result.get("current_phase_output", {})
    await ws.broadcast(conv_id, {
        "type": "squad_phase_result", "message_id": message_id,
        "execution_id": execution_id,
        "phase": result.get("current_phase", 1),
        "phase_name": result.get("current_phase_name", ""),
        "results": phase_output,
    })
    await ws.broadcast(conv_id, {
        "type": "squad_hitl_pause", "message_id": message_id,
        "execution_id": execution_id,
        "phase": result.get("current_phase", 1),
        "phase_name": result.get("current_phase_name", ""),
        "phase_output": phase_output,
        "total_phases": result.get("total_phases", 0),
    })

    # 记录中间 phase 的 token 用量
    _record_token_usage(
        ctx.db_path, meta.get("squad_name", "Squad"),
        result.get("token_model", ""),
        result.get("token_input", 0),
        result.get("token_output", 0),
    )

    # 更新 metadata
    msg_meta = {
        **meta,
        "hitl_waiting": result.get("hitl_waiting", False),
        "current_phase": result.get("current_phase", 1),
        "current_phase_name": result.get("current_phase_name", ""),
        "reasoning": reasoning_text,
    }
    update_message_status(ctx.db_path, message_id, "running", metadata=msg_meta)
    await ws.broadcast(conv_id, {
        "type": "status_change", "message_id": message_id,
        "status": "running", "agent_name": meta.get("squad_name", "Squad"),
        "metadata": msg_meta,
    })

    return {"status": result.get("status", "paused"), "hitl_waiting": result.get("hitl_waiting", False)}


# ── Agent 列表（供 @mention） ────────────────────────────────────


@router.get("/api/agents-list")
async def api_agents_list():
    """可用 agent 列表（前端 @mention 用）。"""
    return list_available_agents()


# ── WebSocket ────────────────────────────────────────────────────


@router.websocket("/ws/conversations/{conversation_id}")
async def ws_conversation(ws: WebSocket, conversation_id: str):
    manager = get_ws_manager()
    await manager.connect(conversation_id, ws)

    stopped = False

    async def _heartbeat():
        """每 25 秒发送心跳，保持连接不被中间件/代理断开。"""
        while not stopped:
            await asyncio.sleep(25)
            try:
                await ws.send_json({"type": "ping"})
            except Exception:
                break

    hb_task = asyncio.create_task(_heartbeat())

    try:
        while True:
            data = await ws.receive_text()
            # 客户端可能发心跳 pong 或其他消息，统一忽略
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        stopped = True
        hb_task.cancel()
        manager.disconnect(conversation_id, ws)
