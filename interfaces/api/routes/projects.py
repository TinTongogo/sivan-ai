"""项目管理路由 (API + 页面)。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext

router = APIRouter(tags=["projects"])


def _get_svc(ctx: AppContext):
    from infrastructure.persistence.connection import SQLiteConnectionManager
    from infrastructure.persistence.project_repo import ProjectRepository
    from application.services.project_service import ProjectService
    mgr = SQLiteConnectionManager.get_instance(ctx.db_path)
    repo = ProjectRepository(mgr)
    return ProjectService(repo)


# ── 页面 ──


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/chat")


# ── API ──


@router.get("/api/projects")
async def api_list_projects(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(_get_svc(ctx).list_projects())


@router.post("/api/projects")
async def api_create_project(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    project = _get_svc(ctx).create_project(body)
    return JSONResponse(project, status_code=201)


@router.get("/api/projects/{project_id}")
async def api_get_project(request: Request, project_id: str):
    ctx: AppContext = request.app.state.context
    project = _get_svc(ctx).get_project(project_id)
    if not project:
        return JSONResponse(status_code=404, content={"error": "项目不存在"})
    return JSONResponse(project)


@router.put("/api/projects/{project_id}")
async def api_update_project(request: Request, project_id: str):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    ok = _get_svc(ctx).update_project(project_id, body)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "项目不存在或无变更"})
    return JSONResponse({"success": True})


@router.delete("/api/projects/{project_id}")
async def api_delete_project(request: Request, project_id: str):
    ctx: AppContext = request.app.state.context
    _get_svc(ctx).delete_project(project_id)
    return JSONResponse({"success": True})


@router.post("/api/projects/{project_id}/kbs")
async def api_assign_kb(request: Request, project_id: str):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    kb_name = body.get("kb_name", "")
    if not kb_name:
        return JSONResponse(status_code=400, content={"error": "kb_name 不能为空"})
    _get_svc(ctx).assign_kb(project_id, kb_name)
    return JSONResponse({"success": True})


@router.delete("/api/projects/{project_id}/kbs/{kb_name}")
async def api_unassign_kb(request: Request, project_id: str, kb_name: str):
    ctx: AppContext = request.app.state.context
    _get_svc(ctx).unassign_kb(project_id, kb_name)
    return JSONResponse({"success": True})


@router.get("/api/projects/{project_id}/kbs")
async def api_get_assigned_kbs(request: Request, project_id: str):
    ctx: AppContext = request.app.state.context
    kbs = _get_svc(ctx).get_assigned_kbs(project_id)
    return JSONResponse(kbs)
