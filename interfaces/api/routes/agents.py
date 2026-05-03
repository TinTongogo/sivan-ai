"""智能体管理路由 (API + 页面)。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services import (
    create_agent,
    delete_agent,
    get_agent_detail,
    get_agents_list,
    update_agent,
)

router = APIRouter(tags=["agents"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    ctx: AppContext = request.app.state.context
    agents = get_agents_list(ctx.db_path)
    template = ctx.jinja_env.get_template("agents.html")
    return HTMLResponse(content=template.render(request=request, agents=agents))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/agents")
async def api_agents(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_agents_list(ctx.db_path))


@router.post("/api/agents")
async def api_create_agent(request: Request, agent_data: dict[str, Any]):
    ctx: AppContext = request.app.state.context
    return JSONResponse(create_agent(ctx.db_path, agent_data))


@router.get("/api/agents/{agent_id}")
async def api_agent_detail(request: Request, agent_id: str):
    ctx: AppContext = request.app.state.context
    result = get_agent_detail(ctx.db_path, agent_id)
    if result:
        return JSONResponse(result)
    return JSONResponse({"error": "智能体不存在"}, status_code=404)


@router.put("/api/agents/{agent_id}")
async def api_update_agent(request: Request, agent_id: str, agent_data: dict[str, Any]):
    ctx: AppContext = request.app.state.context
    return JSONResponse(update_agent(ctx.db_path, agent_id, agent_data))


@router.delete("/api/agents/{agent_id}")
async def api_delete_agent(request: Request, agent_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(delete_agent(ctx.db_path, agent_id))
