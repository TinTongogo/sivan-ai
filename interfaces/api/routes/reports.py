"""周报管理路由 (API + 页面)。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services import (
    delete_weekly_report,
    download_weekly_report_html,
    generate_weekly_report,
    get_subscriptions,
    get_weekly_report_detail,
    get_weekly_reports,
    publish_weekly_report,
    subscribe_report,
    unsubscribe_report,
)

router = APIRouter(tags=["reports"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    ctx: AppContext = request.app.state.context
    reports = get_weekly_reports(ctx.db_path, limit=20)
    template = ctx.jinja_env.get_template("reports.html")
    return HTMLResponse(content=template.render(request=request, reports=reports))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/weekly-reports")
async def api_weekly_reports(request: Request, limit: int = 10):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_weekly_reports(ctx.db_path, limit))


@router.get("/api/weekly-reports/{report_id}")
async def api_weekly_report_detail(request: Request, report_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_weekly_report_detail(ctx.db_path, report_id))


@router.post("/api/weekly-reports/generate")
async def api_generate_weekly_report(request: Request, report_data: dict[str, Any]):
    ctx: AppContext = request.app.state.context
    return JSONResponse(generate_weekly_report(ctx.db_path, report_data))


@router.post("/api/weekly-reports/{report_id}/publish")
async def api_publish_weekly_report(request: Request, report_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(publish_weekly_report(ctx.db_path, report_id))


@router.delete("/api/weekly-reports/{report_id}")
async def api_delete_weekly_report(request: Request, report_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(delete_weekly_report(ctx.db_path, report_id))


@router.get("/api/weekly-reports/{report_id}/download")
async def api_download_weekly_report(request: Request, report_id: str):
    ctx: AppContext = request.app.state.context
    result = download_weekly_report_html(ctx.db_path, report_id)
    if not result.get("success"):
        return JSONResponse(result, status_code=404)
    from starlette.responses import HTMLResponse as StarletteHTMLResponse
    return StarletteHTMLResponse(
        content=result["html"],
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
            "Content-Type": "text/html; charset=utf-8",
        },
    )


@router.post("/api/report-subscriptions")
async def api_subscribe_report(request: Request, subscription: dict[str, Any]):
    ctx: AppContext = request.app.state.context
    return JSONResponse(subscribe_report(ctx.db_path, subscription))


@router.delete("/api/report-subscriptions/{email}/{report_type}")
async def api_unsubscribe_report(request: Request, email: str, report_type: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(unsubscribe_report(ctx.db_path, email, report_type))


@router.get("/api/report-subscriptions")
async def api_get_subscriptions(request: Request, email: str | None = None, report_type: str | None = None):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_subscriptions(ctx.db_path, email=email, report_type=report_type))
