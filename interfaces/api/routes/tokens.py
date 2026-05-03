"""Token 统计路由 (API + 页面)。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services import (
    check_budget_alerts,
    delete_token_usage,
    get_token_daily_trend,
    get_token_stats,
    update_token_budget,
)

router = APIRouter(tags=["tokens"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/tokens", response_class=HTMLResponse)
async def tokens_page(request: Request):
    ctx: AppContext = request.app.state.context
    token_stats = get_token_stats(ctx.db_path)
    template = ctx.jinja_env.get_template("tokens.html")
    return HTMLResponse(content=template.render(request=request, token_stats=token_stats))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/tokens")
async def api_tokens(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_token_stats(ctx.db_path))


@router.get("/api/token-daily")
async def api_token_daily(request: Request, range: str = "7d"):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_token_daily_trend(ctx.db_path, period=range))


@router.delete("/api/token-daily")
async def api_delete_token_usage(request: Request, range: str = "7d"):
    """删除指定时间段 Token 数据（连带清理超过 90 天的旧数据）。"""
    ctx: AppContext = request.app.state.context
    result = delete_token_usage(ctx.db_path, period=range)
    if result.get("success"):
        return JSONResponse(result)
    return JSONResponse(status_code=400, content=result)


@router.post("/api/token-budget")
async def api_token_budget(request: Request, budget: dict[str, Any]):
    ctx: AppContext = request.app.state.context
    return JSONResponse(update_token_budget(ctx.db_path, budget))


@router.post("/api/check-budget-alerts")
async def api_check_budget_alerts(request: Request):
    ctx: AppContext = request.app.state.context
    alerts = check_budget_alerts(ctx.db_path)
    return JSONResponse({"alerts": alerts, "count": len(alerts)})
