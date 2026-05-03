"""技能管理路由 (API + 页面)。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services import (
    delete_skill,
    get_agent_skill_usage,
    get_skill_detail,
    get_skill_usage_trend,
    get_skills_list,
    get_skills_stats,
    update_skill,
)

router = APIRouter(tags=["skills"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request):
    ctx: AppContext = request.app.state.context
    skills = get_skills_list(ctx.db_path)
    skills_stats = get_skills_stats(ctx.db_path)
    template = ctx.jinja_env.get_template("skills.html")
    return HTMLResponse(content=template.render(request=request, skills=skills, skills_stats=skills_stats))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/skills")
async def api_skills(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_skills_list(ctx.db_path))


@router.get("/api/skills/{skill_id}")
async def api_skill_detail(request: Request, skill_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_skill_detail(ctx.db_path, skill_id))


@router.get("/api/skills-stats")
async def api_skills_stats(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_skills_stats(ctx.db_path))


@router.get("/api/skill-usage-trend")
async def api_skill_usage_trend(request: Request, range: str = "7d"):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_skill_usage_trend(ctx.db_path, range))


@router.put("/api/skills/{skill_id}")
async def api_update_skill(request: Request, skill_id: str, skill_data: dict[str, Any]):
    ctx: AppContext = request.app.state.context
    return JSONResponse(update_skill(ctx.db_path, skill_id, skill_data))


@router.delete("/api/skills/{skill_id}")
async def api_delete_skill(request: Request, skill_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(delete_skill(ctx.db_path, skill_id))


@router.get("/api/agent-skill-usage")
async def api_agent_skill_usage(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_agent_skill_usage(ctx.db_path))
