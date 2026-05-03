"""执行日志路由。"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services.logs import delete_log, delete_logs_batch, get_log_detail, get_logs, get_logs_stats

router = APIRouter(tags=["logs"])


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """日志管理页面。"""
    ctx: AppContext = request.app.state.context
    template = ctx.jinja_env.get_template("logs.html")
    return HTMLResponse(content=template.render(request=request))


@router.get("/api/logs")
async def api_logs(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    level: str = Query(""),
    source: str = Query(""),
    action: str = Query(""),
    trace_id: str = Query(""),
    q: str = Query(""),
):
    """日志查询 API。"""
    ctx: AppContext = request.app.state.context
    return get_logs(ctx.db_path, limit=limit, offset=offset, level=level, source=source,
                    action=action, trace_id=trace_id, q=q)


@router.get("/api/logs/{log_id}")
async def api_log_detail(request: Request, log_id: int):
    """单条日志详情。"""
    ctx: AppContext = request.app.state.context
    entry = get_log_detail(ctx.db_path, log_id)
    if entry:
        return entry
    return JSONResponse(status_code=404, content={"error": "日志不存在"})


@router.get("/api/logs-stats")
async def api_logs_stats(request: Request):
    """日志统计。"""
    ctx: AppContext = request.app.state.context
    return get_logs_stats(ctx.db_path)


@router.delete("/api/logs/{log_id}")
async def api_delete_log(request: Request, log_id: int):
    """删除单条日志。"""
    ctx: AppContext = request.app.state.context
    ok = delete_log(ctx.db_path, log_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "日志不存在"})
    return {"success": True}


@router.post("/api/logs/batch-delete")
async def api_batch_delete_logs(request: Request):
    """批量删除日志。"""
    ctx: AppContext = request.app.state.context
    body = await request.json()
    log_ids = body.get("log_ids", [])
    if not log_ids or not isinstance(log_ids, list):
        return JSONResponse(status_code=400, content={"error": "请提供 log_ids 列表"})
    deleted = delete_logs_batch(ctx.db_path, log_ids)
    return {"success": True, "deleted": deleted}
