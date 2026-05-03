"""路由分析路由 (API + 页面)。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services import (
    batch_delete_routing_decisions,
    delete_routing_decision,
    get_recent_decisions,
    get_routing_filter_options,
    get_routing_stats,
    get_routing_strategy_trend,
    get_routing_trend,
    submit_routing_feedback,
)

router = APIRouter(tags=["routing"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/routing", response_class=HTMLResponse)
async def routing_page(request: Request):
    ctx: AppContext = request.app.state.context
    routing_stats = get_routing_stats(ctx.db_path)
    template = ctx.jinja_env.get_template("routing.html")
    return HTMLResponse(content=template.render(request=request, routing_stats=routing_stats))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/routing")
async def api_routing(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_routing_stats(ctx.db_path))


@router.get("/api/routing-trend")
async def api_routing_trend(request: Request, range: str = "7d"):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_routing_trend(ctx.db_path, period=range))


@router.get("/api/routing-strategy-trend")
async def api_routing_strategy_trend(request: Request, range: str = "7d"):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_routing_strategy_trend(ctx.db_path, period=range))


@router.get("/api/recent-decisions")
async def api_recent_decisions(request: Request, page: int = 1, size: int = 10,
                                agent: str = "", strategy: str = "", status: str = "",
                                q: str = ""):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_recent_decisions(ctx.db_path, page, size,
                                             agent=agent, strategy=strategy,
                                             status=status, q=q))


@router.get("/api/routing-filters")
async def api_routing_filters(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_routing_filter_options(ctx.db_path))


@router.post("/api/routing-feedback")
async def api_routing_feedback(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    return JSONResponse(submit_routing_feedback(ctx.db_path, body))


@router.delete("/api/routing/decisions/{decision_pk}")
async def api_delete_routing_decision(request: Request, decision_pk: int):
    ctx: AppContext = request.app.state.context
    return JSONResponse(delete_routing_decision(ctx.db_path, decision_pk))


@router.post("/api/routing/decisions/batch-delete")
async def api_batch_delete_routing_decisions(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    return JSONResponse(batch_delete_routing_decisions(ctx.db_path, body.get("ids", [])))
