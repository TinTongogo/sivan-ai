"""记忆管理路由 (API + 页面)。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services import (
    memory_archive,
    memory_batch,
    memory_delete,
    memory_find_by_scope,
    memory_get,
    memory_list,
    memory_retention,
    memory_retention_status,
    memory_search,
    memory_stats,
    memory_store,
    memory_toggle_important,
    memory_unarchive,
    memory_update,
)
from interfaces.api.services.instinct_patterns import (
    instinct_delete,
    instinct_get,
    instinct_list,
    instinct_stats,
    instinct_toggle_active,
)

router = APIRouter(tags=["memory"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request):
    ctx: AppContext = request.app.state.context
    template = ctx.jinja_env.get_template("memory.html")
    return HTMLResponse(content=template.render(request=request))


# ── API ────────────────────────────────────────────────────────

# 注意: 静态路径必须放在参数化路径之前，避免 /stats 等被 {memory_id} 捕获


@router.get("/api/memory/stats")
async def api_memory_stats(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(memory_stats(ctx.db_path))


@router.get("/api/memory")
async def api_memory_list(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    level: str | None = None,
    scope_id: str | None = None,
    is_archived: bool | None = None,
    retention_min: float | None = None,
    retention_max: float | None = None,
    keyword: str | None = None,
    sort_by: str = "last_accessed_at",
    sort_desc: bool = True,
):
    ctx: AppContext = request.app.state.context
    return JSONResponse(memory_list(
        ctx.db_path, page=page, page_size=page_size,
        level=level, scope_id=scope_id, is_archived=is_archived,
        retention_min=retention_min, retention_max=retention_max,
        keyword=keyword, sort_by=sort_by, sort_desc=sort_desc,
    ))


@router.post("/api/memory")
async def api_memory_store(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    result = memory_store(
        ctx.db_path,
        content=body.get("content", ""),
        level=body.get("level", "session"),
        scope_id=body.get("scope_id", ""),
        metadata=body.get("metadata"),
    )
    if "error" in result:
        return JSONResponse(result, status_code=500)
    return JSONResponse(result)


@router.post("/api/memory/search")
async def api_memory_search(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    results = memory_search(
        ctx.db_path,
        query_text=body.get("query_text", ""),
        level=body.get("level"),
        scope_id=body.get("scope_id"),
        limit=body.get("limit", 10),
        include_archived=body.get("include_archived", True),
    )
    return JSONResponse(results)


@router.post("/api/memory/archive")
async def api_memory_archive(request: Request, threshold: float = 0.15):
    ctx: AppContext = request.app.state.context
    return JSONResponse(memory_archive(ctx.db_path, threshold))


@router.post("/api/memory/batch")
async def api_memory_batch(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    return JSONResponse(memory_batch(
        ctx.db_path,
        action=body.get("action", ""),
        memory_ids=body.get("memory_ids", []),
    ))


@router.post("/api/memory/unarchive/{memory_id}")
async def api_memory_unarchive(request: Request, memory_id: str):
    ctx: AppContext = request.app.state.context
    result = memory_unarchive(ctx.db_path, memory_id)
    if not result:
        return JSONResponse({"error": "记忆不存在或未归档"}, status_code=404)
    return JSONResponse(result)


@router.get("/api/memory/scope/{level}/{scope_id}")
async def api_memory_scope(request: Request, level: str, scope_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(memory_find_by_scope(ctx.db_path, level, scope_id))


@router.get("/api/memory/retention/level/{level}")
async def api_memory_retention_level(request: Request, level: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(memory_retention_status(ctx.db_path, level))


@router.get("/api/memory/retention/{memory_id}")
async def api_memory_retention(request: Request, memory_id: str):
    ctx: AppContext = request.app.state.context
    result = memory_retention(ctx.db_path, memory_id)
    if not result:
        return JSONResponse({"error": "记忆不存在"}, status_code=404)
    return JSONResponse(result)


@router.get("/api/memory/{memory_id}")
async def api_memory_get(request: Request, memory_id: str):
    ctx: AppContext = request.app.state.context
    result = memory_get(ctx.db_path, memory_id)
    if not result:
        return JSONResponse({"error": "记忆不存在"}, status_code=404)
    return JSONResponse(result)


@router.post("/api/memory/{memory_id}/important")
async def api_memory_toggle_important(request: Request, memory_id: str):
    """切换记忆重要标记。"""
    ctx: AppContext = request.app.state.context
    result = memory_toggle_important(ctx.db_path, memory_id)
    if not result:
        return JSONResponse({"error": "记忆不存在"}, status_code=404)
    return JSONResponse(result)


@router.put("/api/memory/{memory_id}")
async def api_memory_update(request: Request, memory_id: str):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    content = body.get("content")
    metadata = body.get("metadata")
    if content is None and metadata is None:
        return JSONResponse({"error": "至少提供 content 或 metadata"}, status_code=400)
    result = memory_update(ctx.db_path, memory_id, content=content, metadata=metadata)
    if not result:
        return JSONResponse({"error": f"记忆不存在: {memory_id}"}, status_code=404)
    return JSONResponse(result)


@router.delete("/api/memory/{memory_id}")
async def api_memory_delete(request: Request, memory_id: str):
    ctx: AppContext = request.app.state.context
    ok = memory_delete(ctx.db_path, memory_id)
    if not ok:
        return JSONResponse({"error": f"记忆不存在: {memory_id}"}, status_code=404)
    return JSONResponse({"status": "deleted", "memory_id": memory_id})


# ── 本能模板 API ──────────────────────────────────────────────


@router.get("/api/instinct-patterns")
async def api_instinct_patterns(request: Request, page: int = 1, page_size: int = 50):
    ctx: AppContext = request.app.state.context
    return JSONResponse(instinct_list(ctx.db_path, page=page, page_size=page_size))


@router.get("/api/instinct-patterns/stats")
async def api_instinct_patterns_stats(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(instinct_stats(ctx.db_path))


@router.get("/api/instinct-patterns/{pattern_id}")
async def api_instinct_pattern_detail(request: Request, pattern_id: str):
    ctx: AppContext = request.app.state.context
    result = instinct_get(ctx.db_path, pattern_id)
    if not result:
        return JSONResponse({"error": "本能模板不存在"}, status_code=404)
    return JSONResponse(result)


@router.post("/api/instinct-patterns/{pattern_id}/toggle-active")
async def api_instinct_toggle_active(request: Request, pattern_id: str):
    ctx: AppContext = request.app.state.context
    result = instinct_toggle_active(ctx.db_path, pattern_id)
    if not result:
        return JSONResponse({"error": "本能模板不存在"}, status_code=404)
    return JSONResponse(result)


@router.delete("/api/instinct-patterns/{pattern_id}")
async def api_instinct_delete(request: Request, pattern_id: str):
    ctx: AppContext = request.app.state.context
    ok = instinct_delete(ctx.db_path, pattern_id)
    if not ok:
        return JSONResponse({"error": f"本能模板不存在: {pattern_id}"}, status_code=404)
    return JSONResponse({"status": "deleted", "pattern_id": pattern_id})
