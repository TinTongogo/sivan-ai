"""契约管理路由 (API + 页面)。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services import (
    delete_contract,
    delete_contracts_batch,
    get_contract_detail,
    get_contract_graph,
    get_contracts_list,
)

router = APIRouter(tags=["contracts"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/contracts", response_class=HTMLResponse)
async def contracts_page(request: Request):
    ctx: AppContext = request.app.state.context
    contracts = get_contracts_list(ctx.db_path)
    template = ctx.jinja_env.get_template("contracts.html")
    return HTMLResponse(content=template.render(request=request, contracts=contracts))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/contracts")
async def api_contracts(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_contracts_list(ctx.db_path))


@router.post("/api/contracts/batch-delete")
async def api_batch_delete_contracts(request: Request):
    ctx: AppContext = request.app.state.context
    body = await request.json()
    cids = body.get("contract_ids", [])
    if not cids or not isinstance(cids, list):
        return JSONResponse(status_code=400, content={"error": "请提供 contract_ids 列表"})
    return JSONResponse(delete_contracts_batch(ctx.db_path, cids))


@router.delete("/api/contracts/{contract_id}")
async def api_delete_contract(request: Request, contract_id: str):
    ctx: AppContext = request.app.state.context
    ok = delete_contract(ctx.db_path, contract_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "契约不存在"})
    return JSONResponse({"success": True})


@router.get("/api/contracts/{contract_id}")
async def api_contract_detail(request: Request, contract_id: str):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_contract_detail(ctx.db_path, contract_id))


@router.get("/api/contract-graph")
async def api_contract_graph(request: Request):
    ctx: AppContext = request.app.state.context
    return JSONResponse(get_contract_graph(ctx.db_path))
