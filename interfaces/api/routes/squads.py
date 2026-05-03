"""Squad 管理路由 (API + 页面)。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services import (
    advance_squad_execution,
    create_squad,
    delete_squad,
    delete_squads_batch,
    execute_squad_hitl,
    execute_squad_impl,
    get_orchestration_pattern,
    get_orchestration_patterns,
    get_squad_detail,
    get_squad_execution_detail,
    get_squad_executions,
    get_squads_list,
    get_squads_stats,
    update_squad,
)
from interfaces.api.services.topology_feedback import (
    topology_feedback_list,
    topology_feedback_record,
    topology_feedback_stats,
)

router = APIRouter(tags=["squads"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/squads", response_class=HTMLResponse)
async def squads_page(request: Request):
    ctx: AppContext = request.app.state.context
    squads = get_squads_list(ctx.db_path)
    squads_stats = get_squads_stats(ctx.db_path)
    template = ctx.jinja_env.get_template("squads.html")
    return HTMLResponse(content=template.render(request=request, squads=squads, squads_stats=squads_stats))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/squads")
async def api_squads(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_squads_list(ctx.db_path))


@router.get("/api/squads/{squad_id}")
async def api_squad_detail(request: Request, squad_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_squad_detail(ctx.db_path, squad_id))


@router.get("/api/squads-stats")
async def api_squads_stats(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_squads_stats(ctx.db_path))


@router.post("/api/squads")
async def api_create_squad(request: Request, squad_data: dict[str, Any]):
    ctx: AppContext = request.app.state.context
    return JSONResponse(create_squad(ctx.db_path, squad_data))


@router.put("/api/squads/{squad_id}")
async def api_update_squad(request: Request, squad_id: str, squad_data: dict[str, Any]):
    ctx: AppContext = request.app.state.context
    return JSONResponse(update_squad(ctx.db_path, squad_id, squad_data))


@router.delete("/api/squads/{squad_id}")
async def api_delete_squad(request: Request, squad_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(delete_squad(ctx.db_path, squad_id))


@router.post("/api/squads/{squad_id}/execute")
async def api_execute_squad(request: Request, squad_id: str, execution_data: dict[str, Any]):
    """执行 Squad。支持 HITL 模式 (execution_data.hitl_enabled=true)。"""
    ctx: AppContext = request.app.state.context
    if execution_data.get("hitl_enabled"):
        return JSONResponse(execute_squad_hitl(ctx.db_path, squad_id, execution_data))
    return JSONResponse(execute_squad_impl(ctx.db_path, squad_id, execution_data))


@router.post("/api/squad-executions/{execution_id}/advance")
async def api_advance_execution(request: Request, execution_id: str):
    """推进 HITL 暂停的执行：continue / correct / abort。"""
    ctx: AppContext = request.app.state.context
    body = await request.json()
    action = body.get("action", "continue")
    correction = body.get("correction_text")
    return JSONResponse(advance_squad_execution(ctx.db_path, execution_id, action, correction))


@router.get("/api/squad-executions")
async def api_squad_executions(request: Request, status: str = None, limit: int = 50):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_squad_executions(ctx.db_path, status, limit))


@router.get("/api/squad-executions/{execution_id}")
async def api_squad_execution_detail(request: Request, execution_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_squad_execution_detail(ctx.db_path, execution_id))


@router.get("/api/orchestration-patterns")
async def api_orchestration_patterns(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_orchestration_patterns(ctx.db_path))


@router.get("/api/orchestration-patterns/{pattern_id}")
async def api_orchestration_pattern(request: Request, pattern_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_orchestration_pattern(ctx.db_path, pattern_id))


@router.post("/api/squads/batch-delete")
async def api_batch_delete_squads(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    sids = body.get("squad_ids", [])
    if not sids or not isinstance(sids, list):
        return JSONResponse(status_code=400, content={"error": "请提供 squad_ids 列表"})
    return JSONResponse(delete_squads_batch(ctx.db_path, sids))


# ── 拓扑反馈 API ──────────────────────────────────────────────


@router.get("/api/topology-feedback/stats")
async def api_topology_feedback_stats(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(topology_feedback_stats(ctx.db_path))


@router.get("/api/topology-feedback")
async def api_topology_feedback_list(request: Request, limit: int = 50):
    ctx: AppContext = request.app.state.context
    return JSONResponse(topology_feedback_list(ctx.db_path, limit=limit))


@router.post("/api/topology-feedback")
async def api_topology_feedback_record(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    result = topology_feedback_record(
        ctx.db_path,
        task_signature=body.get("task_signature", ""),
        topology=body.get("topology", {}),
        satisfaction=body.get("satisfaction", 0.0),
        execution_id=body.get("execution_id", ""),
    )
    if "error" in result:
        return JSONResponse(result, status_code=500)
    return JSONResponse(result)
