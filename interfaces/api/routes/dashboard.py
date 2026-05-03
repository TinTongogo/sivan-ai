"""仪表板 & 系统监控路由 (API + 页面)。"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

import psutil
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import PROJECT_ROOT, AppContext
from interfaces.api.services import (
    get_agents_list,
    get_contracts_list,
    get_recent_decisions,
    get_skills_list,
    get_squads_list,
    get_system_stats,
    get_token_stats,
)

router = APIRouter(tags=["dashboard"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    ctx: AppContext = request.app.state.context
    stats = get_system_stats(ctx.db_path)
    template = ctx.jinja_env.get_template("dashboard.html")
    return HTMLResponse(content=template.render(request=request, stats=stats))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/health")
async def api_health(request: Request):
    ctx: AppContext = request.app.state.context
    db_ok = False
    try:
        conn = __import__("sqlite3").connect(str(ctx.db_path))
        conn.cursor().execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception:
        pass
    return JSONResponse({
        "status": "ok" if db_ok else "degraded",
        "uptime_seconds": ctx.uptime_seconds,
        "database": "connected" if db_ok else "error",
        "routing_db": "connected" if db_ok else "not_available",
        "version": "v1.0.0",
        "timestamp": datetime.now().isoformat(),
    })


@router.get("/api/system-resources")
async def api_system_resources():
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(PROJECT_ROOT))
        proc = psutil.Process()
        return JSONResponse({
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "cpu_count": psutil.cpu_count(),
            "memory_percent": round(mem.percent, 1),
            "memory_used_mb": round(mem.used / 1024 / 1024, 1),
            "memory_total_mb": round(mem.total / 1024 / 1024, 1),
            "disk_percent": round(disk.percent, 1),
            "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "process_memory_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/stats")
async def api_stats(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_system_stats(ctx.db_path))


@router.get("/api/export/{data_type}")
async def api_export_data(request: Request, data_type: str, format: str = "csv"):
    """导出数据（CSV/JSON）。"""
    ctx: AppContext = request.app.state.context

    data_map = {
        "routing": (get_recent_decisions(ctx.db_path, 1, 10000).get("data", []), [
            ("id", "ID"), ("task_description", "任务描述"), ("selected_agent", "选中智能体"),
            ("routing_strategy", "路由策略"), ("confidence_score", "置信度"),
            ("status", "状态"), ("execution_time_ms", "执行时间(ms)"), ("created_at", "创建时间"),
        ]),
        "tokens": (get_token_stats(ctx.db_path).get("recent", []), [
            ("agent_name", "智能体"), ("model", "模型"), ("tokens", "Token数"),
            ("cost", "成本($)"), ("timestamp", "时间"),
        ]),
        "skills": (get_skills_list(ctx.db_path), [
            ("skill_id", "技能ID"), ("name", "名称"), ("display_name", "显示名称"),
            ("category", "分类"), ("maintainer_agent", "维护智能体"),
            ("usage_count", "使用次数"), ("last_used", "最后使用"),
        ]),
        "contracts": (get_contracts_list(ctx.db_path), [
            ("contract_id", "契约ID"), ("contract_type", "类型"), ("status", "状态"),
            ("version", "版本"), ("created_by", "创建者"), ("created_at", "创建时间"),
        ]),
        "agents": (get_agents_list(ctx.db_path), [
            ("name", "名称"), ("display_name", "显示名称"), ("description", "描述"),
        ]),
        "squads": (get_squads_list(ctx.db_path), [
            ("squad_id", "SquadID"), ("name", "名称"), ("description", "描述"),
            ("status", "状态"), ("category", "分类"), ("execution_count", "执行次数"),
        ]),
    }

    if data_type not in data_map:
        return JSONResponse({"error": f"不支持的数据类型: {data_type}"}, status_code=400)

    records, fields = data_map[data_type]

    if format == "json":
        return JSONResponse(records)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([label for _, label in fields])
    for record in records:
        row = []
        for key, _ in fields:
            val = record.get(key, "")
            if isinstance(val, dict):
                val = json.dumps(val, ensure_ascii=False)
            row.append(str(val) if val is not None else "")
        writer.writerow(row)

    csv_content = output.getvalue()
    filename = f"sivan_{data_type}_{datetime.now().strftime('%Y%m%d')}.csv"
    from fastapi.responses import Response
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
