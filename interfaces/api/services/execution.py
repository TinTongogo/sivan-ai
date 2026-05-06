"""消息→Agent 执行链路编排服务。

职责：
  - 将用户消息路由到 orchestrator 决策
  - 根据决策执行 chat / single agent / squad / dynamic squad
  - WebSocket 流式推送执行状态

此模块为 interfaces 层服务，依赖 ws_manager、squads、repos 等 interfaces/infrastructure 组件。
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback as _traceback
from collections.abc import Callable
from logging import getLogger
from pathlib import Path
from typing import Any

from infrastructure.logging.db_logger import get_db_logger
from infrastructure.persistence.conversation_repo import (
    ConversationAgentRepository,
    ConversationRepository,
    MessageRepository,
)
from infrastructure.persistence.token_repo import TokenUsageRepository
from interfaces.api.services.ws_manager import get_ws_manager

logger = getLogger("sivan.execution")


# ── Orchestrator 决策解析 ──────────────────────────────────────────


def parse_orchestrator_decision(result: str) -> dict:
    """解析 orchestrator 返回的 JSON 决策，非 JSON 时视为 chat 回退。"""
    try:
        data = json.loads(result)
        if isinstance(data, dict) and "decision" in data:
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    if result.startswith("[") or result.startswith("任务失败"):
        return {"decision": "chat", "response": f"Orchestrator 分析异常: {result[:200]}"}
    return {"decision": "chat", "response": result}


# ── Token 用量记录 ────────────────────────────────────────────────


def _record_token_usage(
    db_path: str | Path,
    agent_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    task_preview: str = "",
) -> None:
    """记录 token 使用到统计表（兼容旧接口，内部委托 TokenUsageRepository）。"""
    from infrastructure.persistence.connection import SQLiteConnectionManager

    try:
        conn_mgr = SQLiteConnectionManager.get_instance(str(db_path))
        repo = TokenUsageRepository(conn_mgr)
        repo.record_usage(agent_name, model, input_tokens, output_tokens, task_preview[:200] if task_preview else "")
    except Exception as exc:
        logger.warning("记录 token 用量失败: %s", exc)


# ── 执行结束收尾 ──────────────────────────────────────────────────


async def _finalize_response(
    db_path: str | Path,
    conversation_id: str,
    message_id: str,
    content: str,
    agent_name: str,
    trace_id: str,
    ws: Any,
    db_log: Any,
    elapsed_ms: int = 0,
    token_input: int = 0,
    token_output: int = 0,
    token_model: str = "",
    reasoning: str = "",
) -> None:
    """结束消息执行：更新状态 + WebSocket 广播。"""
    meta: dict[str, Any] = {
        "agent": agent_name,
        "trace_id": trace_id,
        "elapsed_ms": elapsed_ms,
    }
    if token_input or token_output:
        meta["token_input"] = token_input
        meta["token_output"] = token_output
        meta["token_used"] = token_input + token_output
    if token_model:
        meta["model"] = token_model
    if reasoning:
        meta["reasoning"] = reasoning

    conn_mgr = _get_conn_mgr(db_path)
    MessageRepository(conn_mgr).update_status(
        message_id,
        "completed",
        content=content,
        metadata=meta,
        trace_id=trace_id,
    )
    _record_token_usage(
        db_path,
        agent_name,
        token_model or agent_name,
        token_input,
        token_output,
        (content or "")[:200],
    )

    asyncio.run_coroutine_threadsafe(
        ws.broadcast(
            conversation_id,
            {
                "type": "status_change",
                "message_id": message_id,
                "status": "completed",
                "content": content,
                "agent_name": agent_name,
                "metadata": meta,
                "trace_id": trace_id,
            },
        ),
        asyncio.get_running_loop(),
    )
    db_log.log(
        "INFO",
        "conversation",
        "msg_exec_complete",
        f"msg={message_id[:8]}, agent={agent_name}",
        trace_id=trace_id,
        metadata={"conversation_id": conversation_id, "message_id": message_id},
    )


# ── 核心执行链路 ──────────────────────────────────────────────────


def _get_conn_mgr(db_path: str | Path):
    """获取 SQLiteConnectionManager 单例（延迟导入避免循环依赖）。"""
    from infrastructure.persistence.connection import SQLiteConnectionManager

    return SQLiteConnectionManager.get_instance(str(db_path))


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
    db_log = get_db_logger()
    ws = get_ws_manager()
    conn_mgr = _get_conn_mgr(db_path)
    msg_repo = MessageRepository(conn_mgr)

    msg = msg_repo.find_by_id(message_id)
    user_msg = msg_repo.find_by_id(user_message_id)
    if not msg or not user_msg:
        return
    user_content = user_msg["content"]

    # ── 链路起点 ──
    trace_id, _ = db_log.trace(
        "conversation",
        "msg_exec_entry",
        f"msg={message_id[:8]}, cid={conversation_id[:8]}, target={target_agent}",
        metadata={
            "conversation_id": conversation_id,
            "message_id": message_id,
            "user_message_id": user_message_id,
            "target": target_agent,
            "content_preview": user_content[:100],
        },
    )

    # 加载历史消息用于多轮对话
    current_sort = user_msg.get("sort_order", 0)
    history = await _load_history(msg_repo, conversation_id, user_message_id, message_id, current_sort, trace_id)

    # 引用回复
    user_content = _inject_quoted_reply(msg_repo, user_msg, user_content, trace_id)

    # 检测上一轮使用的智能体
    last_agent = _detect_last_agent(
        msg_repo,
        conversation_id,
        trace_id,
    )

    # 路由信号
    routing_signals = _compute_routing_signals(
        user_content,
        last_agent,
        trace_id,
    )

    # 快速路由：强共识时绕过 orchestrator
    fast_agent = _try_fast_route(routing_signals, target_agent, trace_id)
    if fast_agent:
        resolved = _resolve_agent_name(db_path, fast_agent, None, user_content, trace_id)
        if resolved:
            await _execute_single_agent(
                db_path,
                conversation_id,
                message_id,
                resolved,
                user_content,
                project_id,
                trace_id,
                ws,
                asyncio.get_running_loop(),
                history,
                cancel_check,
            )
            return

    try:
        loop = asyncio.get_running_loop()
        orch_start = time.time()
        orch_context = {
            "target_agent": target_agent,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "project_id": project_id,
            "trace_id": trace_id,
            "_history": history,
            "_routing_signals": routing_signals,
            "_last_agent": last_agent,
        }

        # Orchestrator 决策
        decision, orch_elapsed = await _call_orchestrator(
            user_content,
            orch_context,
            orch_start,
            trace_id,
        )

        # 收集 orchestrator token 用量
        orch_input = orch_context.get("_token_input", 0)
        orch_output = orch_context.get("_token_output", 0)
        orch_model = orch_context.get("_token_model", "")
        orch_reasoning = orch_context.get("_reasoning_content", "")
        if orch_input or orch_output:
            _record_token_usage(db_path, "orchestrator", orch_model, orch_input, orch_output, user_content[:200])

        # === chat 决策 ===
        if decision["decision"] == "chat":
            await _finalize_response(
                db_path,
                conversation_id,
                message_id,
                decision.get("response", ""),
                "orchestrator",
                trace_id,
                ws,
                db_log,
                elapsed_ms=orch_elapsed,
                token_input=orch_input,
                token_output=orch_output,
                token_model=orch_model,
                reasoning=orch_reasoning,
            )
            return

        # === squad 决策 ===
        if decision["decision"] == "squad":
            topology = decision.get("topology", {})
            phases = topology.get("phases", [])
            mode = topology.get("mode", "sequential")
            phase_desc = [p.get("description", f"阶段{p.get('phase', '?')}") for p in phases]
            db_log.log(
                "INFO",
                "conversation",
                "branch_squad",
                f"squad mode={mode}, phases={len(phases)}",
                trace_id=trace_id,
                metadata={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "mode": mode,
                    "phase_count": len(phases),
                    "phases": phase_desc,
                },
            )
            await _execute_dynamic_squad_flow(
                db_path,
                conversation_id,
                message_id,
                user_message_id,
                topology,
                user_content,
                trace_id,
                ws,
                cancel_check,
                loop,
            )
            return

        # === single 决策 ===
        agent_name = decision.get("agent", "") if decision.get("decision") == "single" else ""
        refined = decision.get("refined_task", "")
        if not agent_name:
            fallback = decision.get("response") or decision.get("reasoning") or orch_reasoning or "无法确定目标智能体"
            db_log.log(
                "WARN",
                "conversation",
                "branch_single_empty_agent",
                "single with empty agent, fallback to chat",
                trace_id=trace_id,
                metadata={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "fallback_response_preview": fallback[:100],
                },
            )
            await _finalize_response(
                db_path,
                conversation_id,
                message_id,
                fallback,
                "orchestrator",
                trace_id,
                ws,
                db_log,
                elapsed_ms=orch_elapsed,
                token_input=orch_input,
                token_output=orch_output,
                token_model=orch_model,
                reasoning=orch_reasoning,
            )
            return

        if refined:
            user_content = refined
            db_log.log(
                "INFO",
                "conversation",
                "task_refined",
                "refined by orchestrator",
                trace_id=trace_id,
                metadata={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "original": decision.get("refined_task", "")[:100],
                    "refined_preview": user_content[:100],
                },
            )

        # AgentResolver 解析
        agent_name = _resolve_agent_name(
            db_path,
            agent_name,
            target_agent,
            user_content,
            trace_id,
        )
        if not agent_name:
            await _finalize_response(
                db_path,
                conversation_id,
                message_id,
                f"未找到匹配的智能体: {decision.get('agent', '')}",
                "orchestrator",
                trace_id,
                ws,
                db_log,
                elapsed_ms=orch_elapsed,
                token_input=orch_input,
                token_output=orch_output,
                token_model=orch_model,
                reasoning=orch_reasoning,
            )
            return

        await _execute_single_agent(
            db_path,
            conversation_id,
            message_id,
            agent_name,
            user_content,
            project_id,
            trace_id,
            ws,
            loop,
            history,
            cancel_check,
        )
    except Exception as _exc:
        _tb = _traceback.format_exc()
        db_log.log(
            "ERROR",
            "conversation",
            "msg_exec_crash",
            f"msg={message_id[:8]} crashed: {_tb}",
            trace_id=trace_id,
            metadata={"conversation_id": conversation_id, "message_id": message_id},
        )
        _err_msg = f"执行异常: {type(_exc).__name__}: {_exc}"
        try:
            msg_repo.update_status(message_id, "failed", content=_err_msg, trace_id=trace_id)
            await ws.broadcast(
                conversation_id,
                {
                    "type": "status_change",
                    "message_id": message_id,
                    "status": "failed",
                    "content": _err_msg,
                    "trace_id": trace_id,
                },
            )
        except Exception:  # noqa: S110
            pass


# ── 内部辅助 ──────────────────────────────────────────────────────


async def _load_history(
    msg_repo: MessageRepository,
    conversation_id: str,
    user_message_id: str,
    agent_message_id: str,
    current_sort: int,
    trace_id: str,
) -> list[dict[str, str]]:
    """加载已完成的历史消息作为多轮对话上下文。

    用 sort_order 做边界过滤，防止 regenerate 时引入后续轮次的消息。
    """
    db_log = get_db_logger()
    history: list[dict[str, str]] = []
    try:
        all_msgs = msg_repo.find_by_conversation(conversation_id)
        for m in all_msgs:
            mid = m["message_id"]
            if mid == user_message_id or mid == agent_message_id:
                continue
            if m.get("sort_order", 0) >= current_sort:
                continue
            if m.get("status") == "completed" and m.get("content"):
                role = "user" if m["role"] == "user" else "assistant"
                history.append({"role": role, "content": m["content"]})
        db_log.log(
            "INFO",
            "conversation",
            "history_loaded",
            f"history={len(history)} msgs, sort_boundary={current_sort}",
            trace_id=trace_id,
            metadata={
                "conversation_id": conversation_id,
                "message_id": agent_message_id,
                "history_count": len(history),
            },
        )
    except Exception as exc:
        db_log.log(
            "WARN",
            "conversation",
            "history_failed",
            f"history load failed: {exc}",
            trace_id=trace_id,
            metadata={"conversation_id": conversation_id, "message_id": agent_message_id},
        )
    return history


def _inject_quoted_reply(
    msg_repo: MessageRepository,
    user_msg: dict[str, Any],
    user_content: str,
    trace_id: str,
) -> str:
    """将引用回复的消息内容注入到当前用户消息上下文。"""
    db_log = get_db_logger()
    try:
        reply_to_id = (user_msg.get("metadata") or {}).get("reply_to_id")
        if reply_to_id:
            quoted = msg_repo.find_by_id(reply_to_id)
            if quoted and quoted.get("content"):
                quoted_content = quoted["content"][:500]
                quoted_role = "用户" if quoted.get("role") == "user" else "智能体"
                quoted_name = quoted.get("agent_name") or quoted_role
                user_content = f"【引用 {quoted_name} 的消息】\n{quoted_content}\n\n---\n{user_content}"
                db_log.log(
                    "INFO",
                    "conversation",
                    "quote_injected",
                    f"reply_to={reply_to_id[:8]}, role={quoted_role}",
                    trace_id=trace_id,
                    metadata={
                        "message_id": user_msg.get("message_id", ""),
                        "reply_to": reply_to_id,
                        "quoted_role": quoted_role,
                    },
                )
    except Exception:  # noqa: S110
        pass
    return user_content


def _detect_last_agent(
    msg_repo: MessageRepository,
    conversation_id: str,
    trace_id: str,
) -> str | None:
    """检测上一轮使用的非 orchestrator 智能体，供路由系统参考。"""
    db_log = get_db_logger()
    last_agent = None
    try:
        all_msgs = msg_repo.find_by_conversation(conversation_id)
        for m in reversed(all_msgs):
            if m["role"] == "agent" and m.get("status") == "completed" and m.get("content"):
                aid = m.get("agent_name") or ""
                if aid and aid != "orchestrator":
                    last_agent = aid
                    break
        if last_agent:
            logger.info("上一轮智能体[%s]: %s", trace_id[:8], last_agent)
            db_log.log(
                "INFO",
                "conversation",
                "last_agent_detected",
                f"last_agent={last_agent}",
                trace_id=trace_id,
                metadata={"conversation_id": conversation_id, "last_agent": last_agent},
            )
    except Exception:  # noqa: S110
        pass
    return last_agent


def _compute_routing_signals(
    user_content: str,
    last_agent: str | None,
    trace_id: str,
) -> dict | None:
    """调用路由系统获取各策略推荐信号，作为 orchestrator 决策的输入。"""
    db_log = get_db_logger()
    try:
        from interfaces.mcp.server import get_system

        system = get_system()
        if system and hasattr(system, "routing_service"):
            routing_ctx: dict[str, Any] = {"source": "conversation"}
            if last_agent:
                routing_ctx["session_context"] = f"上一轮使用的智能体: {last_agent}"
            routing_signals = system.routing_service.route_with_all_strategies(
                user_content,
                routing_ctx,
            )
            adaptive = routing_signals.get("adaptive")
            consensus = routing_signals.get("consensus")
            strategies = routing_signals.get("strategies", {})
            strategy_details = {k: v.get("selected_agent") for k, v in strategies.items()}
            logger.info(
                "路由信号[%s]: adaptive=%s, consensus=%s, details=%s",
                trace_id[:8],
                adaptive,
                consensus,
                strategy_details,
            )
            db_log.log(
                "INFO",
                "routing",
                "signal_computed",
                f"adaptive={adaptive}, consensus={consensus}",
                trace_id=trace_id,
                metadata={"adaptive": adaptive, "consensus": consensus, "strategies": strategy_details},
            )
            return routing_signals
    except Exception as exc:
        db_log.log("WARN", "routing", "signal_failed", f"routing signal failed: {exc}", trace_id=trace_id, metadata={})
        logger.debug("路由信号计算失败（不影响主流程）: %s", exc)
    return None


async def _call_orchestrator(
    user_content: str,
    orch_context: dict,
    orch_start: float,
    trace_id: str,
) -> tuple[dict, int]:
    """调用 orchestrator agent 做决策，返回 (decision_dict, elapsed_ms)。"""
    from interfaces.api.services.squads import call_agent_for_squad

    db_log = get_db_logger()
    try:
        orch_result = await asyncio.wait_for(
            asyncio.to_thread(call_agent_for_squad, "orchestrator", user_content, orch_context),
            timeout=120,
        )
    except TimeoutError:
        orch_result = json.dumps(
            {
                "decision": "chat",
                "response": "[超时] 智能体分析超时，请稍后重试",
                "reasoning": "orchestrator LLM 调用超时",
            }
        )
    orch_elapsed = int((time.time() - orch_start) * 1000)
    decision = parse_orchestrator_decision(orch_result)
    db_log.log(
        "INFO",
        "orchestrator",
        "decision_made",
        f"decision={decision.get('decision')}, elapsed_ms={orch_elapsed}",
        trace_id=trace_id,
        metadata={
            "decision": decision.get("decision"),
            "agent": decision.get("agent", ""),
            "refined_task": (decision.get("refined_task", "") or "")[:100],
            "elapsed_ms": orch_elapsed,
        },
    )
    return decision, orch_elapsed


def _resolve_agent_name(
    db_path: str | Path,
    agent_name: str,
    target_agent: str | None,
    user_content: str,
    trace_id: str,
) -> str | None:
    """解析 LLM 输出的语义化 agent 名称，返回最终 agent_name 或 None。"""
    if target_agent:
        return target_agent
    if agent_name == "orchestrator":
        return agent_name

    from application.services.agent_resolver import AgentResolver
    from interfaces.mcp.server import get_system

    db_log = get_db_logger()

    resolver = AgentResolver(db_path)
    resolved = resolver.resolve_agent(agent_name)
    if resolved:
        logger.info("AgentResolver[%s]: '%s' → 已注册 '%s'", trace_id[:8], agent_name, resolved)
        db_log.log(
            "INFO",
            "conversation",
            "resolver_resolved",
            f"'{agent_name}' → '{resolved}'",
            trace_id=trace_id,
            metadata={"original": agent_name, "resolved": resolved, "action": "matched"},
        )
        return resolved
    if resolver._should_create_agent(agent_name):
        new_id = resolver.create_agent(agent_name, task_description=user_content)
        logger.info("AgentResolver[%s]: '%s' → 新创建 '%s'", trace_id[:8], agent_name, new_id)
        db_log.log(
            "INFO",
            "conversation",
            "resolver_created",
            f"'{agent_name}' → new '{new_id}'",
            trace_id=trace_id,
            metadata={"original": agent_name, "resolved": new_id, "action": "created"},
        )
        get_system().agent_service.reload(new_id)
        return new_id

    db_log.log(
        "WARN",
        "conversation",
        "resolver_not_found",
        f"no match for '{agent_name}', skip create",
        trace_id=trace_id,
        metadata={"agent_name": agent_name, "action": "not_found"},
    )
    return None


def _build_stream_callbacks(
    conversation_id: str,
    message_id: str,
    agent_name: str,
    trace_id: str,
    ws: Any,
    loop: asyncio.AbstractEventLoop,
    cancel_check: Callable[[], bool] | None,
) -> tuple[Callable[[str], None], Callable[[str], None]]:
    """构造流式推送回调 (stream_callback, reasoning_callback)。

    两个回调分别在普通内容和思考内容到达时通过 WebSocket 推送。
    """

    def stream_callback(chunk: str) -> None:
        if cancel_check and cancel_check():
            return
        asyncio.run_coroutine_threadsafe(
            ws.broadcast(
                conversation_id,
                {
                    "type": "message_chunk",
                    "message_id": message_id,
                    "agent_name": agent_name,
                    "content": chunk,
                    "trace_id": trace_id,
                },
            ),
            loop,
        )

    def reasoning_callback(chunk: str) -> None:
        if cancel_check and cancel_check():
            return
        asyncio.run_coroutine_threadsafe(
            ws.broadcast(
                conversation_id,
                {
                    "type": "reasoning_chunk",
                    "message_id": message_id,
                    "agent_name": agent_name,
                    "content": chunk,
                    "trace_id": trace_id,
                },
            ),
            loop,
        )

    return stream_callback, reasoning_callback


async def _execute_agent_call(
    agent_name: str,
    task: str,
    context: dict,
    trace_id: str,
) -> str:
    """调用目标 agent 执行任务，返回结果字符串，超时或异常时返回错误消息。"""
    from interfaces.api.services.squads import call_agent_for_squad

    db_log = get_db_logger()
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(call_agent_for_squad, agent_name, task, context),
            timeout=300,
        )
    except TimeoutError:
        db_log.log(
            "WARN",
            "conversation",
            "exec_timeout",
            f"agent={agent_name}, timeout=300s",
            trace_id=trace_id,
            metadata={"agent": agent_name, "timeout": 300},
        )
        return "[错误] 执行超时"
    except Exception as exc:
        db_log.log(
            "ERROR",
            "conversation",
            "exec_failed",
            f"agent={agent_name}: {exc}",
            trace_id=trace_id,
            metadata={"agent": agent_name, "error": str(exc)[:500]},
        )
        return f"[错误] {exc}"


def _try_fast_route(
    routing_signals: dict | None,
    target_agent: str | None,
    trace_id: str,
) -> str | None:
    """检查是否可以绕过 orchestrator 直接路由。返回 agent_name 或 None。"""
    if target_agent:
        logger.info("快速路由[%s]: 用户指定 target=%s", trace_id[:8], target_agent)
        return target_agent
    if not routing_signals:
        return None
    strategies = routing_signals.get("strategies", {})
    adaptive = routing_signals.get("adaptive")
    if not adaptive:
        return None
    base_names = {"semantic", "ml", "context_aware"}
    votes: dict[str, int] = {}
    for name in base_names:
        agent = strategies.get(name, {}).get("selected_agent")
        if agent:
            votes[agent] = votes.get(agent, 0) + 1
    if not votes:
        return None
    winner = max(votes, key=votes.get)
    if votes[winner] >= 2 and winner == adaptive:
        logger.info(
            "快速路由[%s]: 强共识 agent=%s (%d/3 base + adaptive)",
            trace_id[:8],
            winner,
            votes[winner],
        )
        return winner
    return None


async def _execute_single_agent(
    db_path: str | Path,
    conversation_id: str,
    message_id: str,
    agent_name: str,
    task: str,
    project_id: str,
    trace_id: str,
    ws: Any,
    loop: asyncio.AbstractEventLoop,
    history: list[dict[str, str]],
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    """执行单个 agent：更新 running → 构建回调 → 调用 agent → 取消检查 → 完成推送。"""
    db_log = get_db_logger()
    conn_mgr = _get_conn_mgr(db_path)
    msg_repo = MessageRepository(conn_mgr)

    db_log.log(
        "INFO",
        "conversation",
        "agent_exec_start",
        f"agent={agent_name}, task_preview={task[:100]}",
        trace_id=trace_id,
        metadata={
            "conversation_id": conversation_id,
            "message_id": message_id,
            "agent": agent_name,
            "task_preview": task[:100],
        },
    )
    msg_repo.update_status(message_id, "running", agent_name=agent_name, trace_id=trace_id)
    ConversationAgentRepository(conn_mgr).ensure(conversation_id, agent_name)
    await ws.broadcast(
        conversation_id,
        {
            "type": "status_change",
            "message_id": message_id,
            "status": "running",
            "agent_name": agent_name,
            "trace_id": trace_id,
        },
    )
    ConversationRepository(conn_mgr).update(conversation_id)

    start = time.time()
    stream_callback, reasoning_callback = _build_stream_callbacks(
        conversation_id,
        message_id,
        agent_name,
        trace_id,
        ws,
        loop,
        cancel_check,
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
    result = await _execute_agent_call(agent_name, task, context, trace_id)

    if cancel_check and cancel_check():
        msg_repo.update_status(message_id, "cancelled", trace_id=trace_id)
        await ws.broadcast(
            conversation_id,
            {
                "type": "status_change",
                "message_id": message_id,
                "status": "cancelled",
                "content": "用户已取消",
                "trace_id": trace_id,
            },
        )
        db_log.log(
            "INFO",
            "conversation",
            "msg_exec_cancelled",
            f"msg={message_id[:8]}, agent={agent_name}",
            trace_id=trace_id,
            metadata={"conversation_id": conversation_id, "message_id": message_id},
        )
        return

    elapsed_ms = int((time.time() - start) * 1000)
    token_used = context.get("_token_used", 0)
    token_input_val = context.get("_token_input", 0)
    token_output_val = context.get("_token_output", 0)
    token_model_val = context.get("_token_model", "")
    reasoning_val = context.get("_reasoning_content", "")
    meta: dict[str, Any] = {
        "elapsed_ms": elapsed_ms,
        "agent": agent_name,
        "token_used": token_used,
        "token_input": token_input_val,
        "token_output": token_output_val,
        "model": token_model_val,
        "trace_id": trace_id,
    }
    if reasoning_val:
        meta["reasoning"] = reasoning_val
    content_str = str(result)
    is_error = content_str.startswith("[错误]") or content_str.startswith("任务失败:")
    status = "failed" if is_error else "completed"
    msg_repo.update_status(message_id, status, content=content_str, metadata=meta, trace_id=trace_id)
    _record_token_usage(
        db_path, agent_name, token_model_val or agent_name, token_input_val, token_output_val, task[:200]
    )
    await ws.broadcast(
        conversation_id,
        {
            "type": "status_change",
            "message_id": message_id,
            "status": status,
            "content": result,
            "agent_name": agent_name,
            "metadata": meta,
            "trace_id": trace_id,
        },
    )
    db_log.log(
        "INFO",
        "conversation",
        "msg_exec_complete",
        f"msg={message_id[:8]}, agent={agent_name}, status={status}, elapsed={elapsed_ms}ms",
        trace_id=trace_id,
        duration_ms=elapsed_ms,
        metadata={
            "conversation_id": conversation_id,
            "message_id": message_id,
            "agent": agent_name,
            "status": status,
            "elapsed_ms": elapsed_ms,
            "token_input": token_input_val,
            "token_output": token_output_val,
            "model": token_model_val,
            "has_reasoning": bool(reasoning_val),
        },
    )


# ── Squad HITL 执行流 ─────────────────────────────────────────────


async def _execute_squad_flow(
    db_path: str | Path,
    conversation_id: str,
    message_id: str,
    user_message_id: str,
    squad_match: Any,
    routed_agent: str,
    trace_id: str,
    ws: Any,
    cancel_check: Any,
    loop: Any,
) -> None:
    """执行 Squad 流（HITL 模式），第一阶段执行后暂停等待用户操作。"""
    from interfaces.api.services.squads import execute_squad_hitl

    db_log = get_db_logger()
    conn_mgr = _get_conn_mgr(db_path)
    msg_repo = MessageRepository(conn_mgr)

    squad_id = squad_match.squad_id
    user_msg = msg_repo.find_by_id(user_message_id)
    user_content = user_msg.get("content", "") if user_msg else ""

    stream_callback, reasoning_callback = _build_stream_callbacks(
        conversation_id,
        message_id,
        squad_match.squad_name,
        trace_id,
        ws,
        loop,
        cancel_check,
    )

    _reasoning_accumulator: list[str] = []

    def _reasoning_cb(chunk: str) -> None:
        _reasoning_accumulator.append(chunk)
        reasoning_callback(chunk)

    meta = {"squad_id": squad_id, "squad_name": squad_match.squad_name, "agent": routed_agent, "trace_id": trace_id}
    msg_repo.update_status(message_id, "running", agent_name=squad_match.squad_name, metadata=meta, trace_id=trace_id)
    ConversationAgentRepository(conn_mgr).ensure(conversation_id, squad_match.squad_name)
    await ws.broadcast(
        conversation_id,
        {
            "type": "status_change",
            "message_id": message_id,
            "status": "running",
            "agent_name": squad_match.squad_name,
            "metadata": meta,
            "trace_id": trace_id,
        },
    )
    ConversationRepository(conn_mgr).update(conversation_id)

    await ws.broadcast(
        conversation_id,
        {
            "type": "squad_phase_start",
            "message_id": message_id,
            "phase": 0,
            "phase_name": "前置检查",
            "agents": [],
            "trace_id": trace_id,
        },
    )

    try:
        start = time.time()
        extra_ctx = {
            "_stream_callback": stream_callback,
            "_reasoning_callback": _reasoning_cb,
            "_squad_execution": True,
            "trace_id": trace_id,
        }
        result = await asyncio.to_thread(
            execute_squad_hitl,
            str(db_path),
            squad_id,
            {
                "description": f"Squad: {squad_match.squad_name}",
                "trigger_type": "conversation",
                "created_by": "user",
                "input_params": {"task": user_content},
            },
            extra_context=extra_ctx,
        )

        if not result.get("success"):
            raise Exception(result.get("error", "Squad 执行启动失败"))

        _record_token_usage(
            db_path,
            squad_match.squad_name,
            result.get("token_model", ""),
            result.get("token_input", 0),
            result.get("token_output", 0),
            user_content[:200],
        )

        execution_id = result["execution_id"]
        elapsed_ms = int((time.time() - start) * 1000)
        hitl_waiting = result.get("hitl_waiting", True)

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

        await ws.broadcast(
            conversation_id,
            {
                "type": "squad_phase_result",
                "message_id": message_id,
                "execution_id": execution_id,
                "phase": result.get("current_phase", 1),
                "phase_name": result.get("current_phase_name", ""),
                "results": phase_output,
                "trace_id": trace_id,
            },
        )

        if hitl_waiting:
            await ws.broadcast(
                conversation_id,
                {
                    "type": "squad_hitl_pause",
                    "message_id": message_id,
                    "execution_id": execution_id,
                    "phase": result.get("current_phase", 1),
                    "phase_name": result.get("current_phase_name", ""),
                    "phase_output": phase_output,
                    "total_phases": result.get("total_phases", 0),
                    "trace_id": trace_id,
                },
            )
            msg_repo.update_status(message_id, "running", metadata=squad_meta, trace_id=trace_id)
            await ws.broadcast(
                conversation_id,
                {
                    "type": "status_change",
                    "message_id": message_id,
                    "status": "running",
                    "agent_name": squad_match.squad_name,
                    "metadata": squad_meta,
                    "trace_id": trace_id,
                },
            )
        else:
            squad_meta["squad_complete"] = True
            phase_outputs = result.get("current_phase_output", {})
            content_parts = []
            if isinstance(phase_outputs, dict):
                for agent_name, text in phase_outputs.items():
                    if text:
                        content_parts.append(f"### {agent_name}\n\n{text}")
            completed_content = (
                "\n\n---\n\n".join(content_parts)
                if content_parts
                else f"Squad 执行完成（共 {result.get('total_phases', 0)} 阶段）"
            )
            squad_meta["elapsed_ms"] = result.get("elapsed_ms", elapsed_ms)
            msg_repo.update_status(
                message_id, "completed", content=completed_content, metadata=squad_meta, trace_id=trace_id
            )
            await ws.broadcast(
                conversation_id,
                {
                    "type": "status_change",
                    "message_id": message_id,
                    "status": "completed",
                    "agent_name": squad_match.squad_name,
                    "content": completed_content,
                    "metadata": squad_meta,
                    "trace_id": trace_id,
                },
            )
            await ws.broadcast(
                conversation_id,
                {
                    "type": "squad_complete",
                    "message_id": message_id,
                    "status": "completed",
                    "execution_id": execution_id,
                    "total_phases": result.get("total_phases", 0),
                },
            )

        db_log.log(
            "INFO",
            "squad",
            "hitl_flow_first_phase_done",
            f"msg={message_id[:8]}, squad={squad_id}, exec={execution_id}",
            trace_id=trace_id,
            duration_ms=elapsed_ms,
            metadata={"execution_id": execution_id, "squad_id": squad_id},
        )

    except Exception as exc:
        _tb_str = _traceback.format_exc()
        db_log.log(
            "ERROR",
            "squad",
            "hitl_flow_failed",
            f"msg={message_id[:8]} squad={squad_id}: {exc}",
            trace_id=trace_id,
            metadata={"squad_id": squad_id, "error": str(exc)[:500]},
        )
        err_msg = f"Squad 执行失败: {exc}"
        msg_repo.update_status(message_id, "failed", content=err_msg, trace_id=trace_id)
        await ws.broadcast(
            conversation_id,
            {
                "type": "status_change",
                "message_id": message_id,
                "status": "failed",
                "content": err_msg,
                "trace_id": trace_id,
            },
        )


# ── 动态 Squad 执行流 ─────────────────────────────────────────────


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

    db_log = get_db_logger()
    conn_mgr = _get_conn_mgr(db_path)
    msg_repo = MessageRepository(conn_mgr)

    phases = topology.get("phases", [])
    mode = topology.get("mode", "sequential")
    squad_name = f"动态编排 ({mode})"

    meta = {"topology_mode": mode, "phase_count": len(phases), "dynamic_squad": True, "trace_id": trace_id}
    msg_repo.update_status(message_id, "running", agent_name=squad_name, metadata=meta, trace_id=trace_id)
    await ws.broadcast(
        conversation_id,
        {
            "type": "status_change",
            "message_id": message_id,
            "status": "running",
            "agent_name": squad_name,
            "metadata": meta,
            "trace_id": trace_id,
        },
    )
    ConversationRepository(conn_mgr).update(conversation_id)

    _reasoning_accumulator: list[str] = []
    stream_callback, reasoning_callback = _build_stream_callbacks(
        conversation_id,
        message_id,
        squad_name,
        trace_id,
        ws,
        loop,
        cancel_check,
    )

    def _reasoning_cb(chunk: str) -> None:
        _reasoning_accumulator.append(chunk)
        reasoning_callback(chunk)

    extra_context = {
        "_stream_callback": stream_callback,
        "_reasoning_callback": _reasoning_cb,
        "trace_id": trace_id,
    }

    try:
        result = await asyncio.to_thread(
            execute_dynamic_squad,
            str(db_path),
            topology,
            user_content,
            extra_context,
        )

        content_parts = []
        for p in phases:
            pn = p.get("phase", "?")
            pd = p.get("description", f"阶段 {pn}")
            agents = p.get("agents", [])
            content_parts.append(f"**{pd}**（{', '.join(agents) if agents else '无智能体'}）")
        summary = (
            "动态编排执行完成\n\n" + "\n\n".join(content_parts)
            if result.get("success")
            else f"动态编排执行异常: {result.get('status', 'unknown')}\n\n" + "\n\n".join(content_parts)
        )

        final_meta = {
            "topology_mode": mode,
            "phase_count": len(phases),
            "dynamic_squad": True,
            "trace_id": trace_id,
            "reasoning": "".join(_reasoning_accumulator),
        }
        final_status = "completed" if result.get("success") else "failed"
        msg_repo.update_status(message_id, final_status, content=summary, metadata=final_meta, trace_id=trace_id)
        await ws.broadcast(
            conversation_id,
            {
                "type": "status_change",
                "message_id": message_id,
                "status": final_status,
                "content": summary,
                "agent_name": squad_name,
                "metadata": final_meta,
                "trace_id": trace_id,
            },
        )
        db_log.log(
            "INFO",
            "conversation",
            "dynamic_squad_complete",
            f"msg={message_id[:8]}, phases={len(phases)}",
            trace_id=trace_id,
            metadata={"topology_mode": mode, "phase_count": len(phases)},
        )
    except Exception as exc:
        _tb_str = _traceback.format_exc()
        db_log.log(
            "ERROR",
            "conversation",
            "dynamic_squad_failed",
            f"msg={message_id[:8]}: {exc}",
            trace_id=trace_id,
            metadata={"error": str(exc)[:500]},
        )
        err_msg = f"动态编排执行失败: {exc}"
        msg_repo.update_status(message_id, "failed", content=err_msg, trace_id=trace_id)
        await ws.broadcast(
            conversation_id,
            {
                "type": "status_change",
                "message_id": message_id,
                "status": "failed",
                "content": err_msg,
                "trace_id": trace_id,
            },
        )


# ── 路由决策记录 ──────────────────────────────────────────────────


def record_squad_routing_decision(
    db_path: str | Path,
    task_description: str,
    squad_match: Any,
    routed_agent: str,
    trace_id: str = "",
    start_time: float | None = None,
) -> None:
    """将 squad 匹配结果记录为路由决策，供路由分析页面展示。"""
    import time as time_module

    from infrastructure.persistence.connection import SQLiteConnectionManager

    conn_mgr = SQLiteConnectionManager.get_instance(str(db_path))

    elapsed_ms = int((time_module.time() - (start_time or time_module.time())) * 1000)
    context = {
        "squad_id": squad_match.squad_id,
        "match_reason": squad_match.match_reason,
        "routed_agent": routed_agent,
        "workflow_type": squad_match.workflow_type,
        "phase_count": squad_match.phase_count,
    }
    try:
        cursor = conn_mgr.execute(
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
        candidates = [
            ("路由智能体匹配", 3, 1),
            ("关键词匹配", 2, 2),
            ("阶段名称匹配", 1, 3),
        ]
        for cname, cscore, crank in candidates:
            conn_mgr.execute(
                "INSERT INTO candidate_scores (decision_id, agent_name, score, rank) VALUES (?, ?, ?, ?)",
                (decision_pk, cname, cscore / 6.0, crank),
            )
        conn_mgr.commit()
    except Exception:  # noqa: S110
        pass


# ── 可用 Agent 列表（供前端 @mention） ─────────────────────────────


def list_available_agents() -> list[dict[str, Any]]:
    """列出所有可用 agent 供前端 @mention 用。"""
    try:
        from interfaces.mcp.server import get_system

        system = get_system()
        if system and hasattr(system, "agent_service"):
            return system.agent_service.list_agents()
    except Exception:  # noqa: S110
        pass
    return []
