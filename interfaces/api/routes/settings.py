"""系统设置路由 (API + 页面)。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services.settings import (
    activate_provider,
    create_provider,
    delete_provider,
    fetch_llm_models,
    fetch_llm_models_for_provider,
    get_all_settings,
    get_llm_settings,
    get_provider_by_id,
    get_providers,
    set_setting,
    test_llm_connection,
    test_llm_connection_with_provider,
    update_provider,
)

router = APIRouter(tags=["settings"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    ctx: AppContext = request.app.state.context
    template = ctx.jinja_env.get_template("settings.html")
    return HTMLResponse(content=template.render(request=request))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/settings")
async def api_get_settings(request: Request):
    ctx: AppContext = request.app.state.context
    settings_list = get_all_settings(ctx.db_path)
    return JSONResponse(content={"settings": settings_list})


@router.get("/api/settings/llm")
async def api_get_llm_settings(request: Request):
    ctx: AppContext = request.app.state.context
    config = get_llm_settings(ctx.db_path)
    return JSONResponse(content=config)


@router.put("/api/settings/{key}")
async def api_update_setting(key: str, request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    value = body.get("value", "")
    set_setting(
        ctx.db_path,
        key,
        value,
        body.get("value_type"),
        body.get("description"),
        body.get("category"),
    )
    return JSONResponse(content={"success": True})


@router.post("/api/settings/batch")
async def api_batch_update(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    settings_data = body.get("settings", [])
    for item in settings_data:
        key = item.get("key")
        value = item.get("value", "")
        if not key:
            continue
        set_setting(
            ctx.db_path,
            key,
            value,
            item.get("value_type"),
            item.get("description"),
            item.get("category"),
        )
    return JSONResponse(content={"success": True})


@router.post("/api/settings/test-llm")
async def api_test_llm(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    provider_id = body.get("provider_id", "")
    # 从 DB 加载已保存的配置作为基线
    saved = get_provider_by_id(ctx.db_path, provider_id) if provider_id else None

    # 用表单值覆盖，空白字段回退到 DB 已保存值
    provider = {
        "auth_type": body.get("auth_type") or (saved.get("auth_type", "OpenAI") if saved else "OpenAI"),
        "api_key": body.get("api_key") or (saved.get("api_key", "") if saved else ""),
        "api_url": body.get("api_url") or (saved.get("api_url", "") if saved else ""),
        "name": body.get("name") or (saved.get("name", provider_id) if saved else provider_id),
        "model": body.get("model") or (saved.get("model", "") if saved else ""),
        "api_version": body.get("api_version") or (saved.get("api_version", "") if saved else ""),
        "max_tokens": int(body.get("max_tokens") or (saved.get("max_tokens", 4096) if saved else 4096)),
        "temperature": float(body.get("temperature") or (saved.get("temperature", 0.7) if saved else 0.7)),
        "timeout": int(body.get("timeout") or (saved.get("timeout", 120) if saved else 120)),
    }

    if not provider["api_url"]:
        # 没有 api_url，回退到全局测试（兼容旧 settings 表）
        if saved:
            return JSONResponse(content={"success": False, "error": "API URL 未配置"})
        result = test_llm_connection(ctx.db_path)
        return JSONResponse(content=result)

    result = test_llm_connection_with_provider(provider)
    return JSONResponse(content=result)


@router.get("/api/settings/llm-models")
async def api_get_llm_models(request: Request):
    ctx: AppContext = request.app.state.context
    provider_id = request.query_params.get("provider_id", "")
    if provider_id:
        provider = get_provider_by_id(ctx.db_path, provider_id)
        if provider:
            models = fetch_llm_models_for_provider(provider)
            return JSONResponse(content={"models": models, "provider_id": provider_id})
    models = fetch_llm_models(ctx.db_path)
    return JSONResponse(content={"models": models})


@router.post("/api/settings/test-llm-models")
async def api_test_llm_models(request: Request):
    """测试成功后拉取模型（使用请求体中的配置，不依赖 DB）。"""
    ctx: AppContext = request.app.state.context
    body = await request.json()
    provider = {
        "auth_type": body.get("auth_type", "OpenAI"),
        "api_key": body.get("api_key", ""),
        "api_url": body.get("api_url", ""),
        "timeout": int(body.get("timeout", 120)),
    }
    models = fetch_llm_models_for_provider(provider)
    return JSONResponse(content={"models": models})


# ── 提供商 CRUD ────────────────────────────────────────────


@router.get("/api/settings/providers")
async def api_list_providers(request: Request):
    ctx: AppContext = request.app.state.context
    providers = get_providers(ctx.db_path)
    return JSONResponse(content={"providers": providers})


@router.post("/api/settings/providers")
async def api_create_provider(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    provider = create_provider(
        ctx.db_path,
        name=body.get("name", ""),
        auth_type=body.get("auth_type", "OpenAI"),
        api_url=body.get("api_url", ""),
        api_key=body.get("api_key", ""),
        model=body.get("model", ""),
        api_version=body.get("api_version", ""),
        max_tokens=int(body.get("max_tokens", 4096)),
        temperature=float(body.get("temperature", 0.7)),
        timeout=int(body.get("timeout", 120)),
    )
    return JSONResponse(content=provider, status_code=201)


@router.put("/api/settings/providers/{provider_id}")
async def api_update_provider(provider_id: str, request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    result = update_provider(ctx.db_path, provider_id, body)
    if result is None:
        return JSONResponse(content={"error": "提供商不存在"}, status_code=404)
    return JSONResponse(content=result)


@router.delete("/api/settings/providers/{provider_id}")
async def api_delete_provider(provider_id: str, request: Request):
    ctx: AppContext = request.app.state.context
    success = delete_provider(ctx.db_path, provider_id)
    if not success:
        return JSONResponse(content={"error": "无法删除（不存在或为激活中）"}, status_code=400)
    return JSONResponse(content={"success": True})


@router.put("/api/settings/providers/{provider_id}/activate")
async def api_activate_provider(provider_id: str, request: Request):
    ctx: AppContext = request.app.state.context
    result = activate_provider(ctx.db_path, provider_id)
    if result is None:
        return JSONResponse(content={"error": "提供商不存在"}, status_code=404)
    return JSONResponse(content=result)
