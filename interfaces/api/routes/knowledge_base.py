"""知识库 REST API 路由。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from interfaces.api.context import AppContext
from interfaces.api.services.knowledge_base import kb_service_for_context
from infrastructure.rag.embedding import BGEChineseEmbedding

router = APIRouter(tags=["knowledge_base"])


# ── 页面 ──────────────────────────────────────────────────────


@router.get("/knowledge-bases", response_class=HTMLResponse)
async def knowledge_base_page(request: Request):
    """知识库管理页面。"""
    ctx: AppContext = request.app.state.context
    template = ctx.jinja_env.get_template("knowledge_bases.html")
    return HTMLResponse(content=template.render(request=request))


# ── API ────────────────────────────────────────────────────────


@router.get("/api/knowledge-bases")
async def api_list_kbs(request: Request, page: int | None = None, page_size: int = 20):
    """列出所有知识库（支持分页）。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    if page is not None:
        return JSONResponse(svc.list_knowledge_bases_paginated(page, page_size))
    return JSONResponse(svc.list_knowledge_bases())


@router.get("/api/knowledge-bases/search-all")
async def api_search_all_kbs(request: Request, q: str = "", top_k: int = 5, mode: str = "vector"):
    """搜索所有知识库。"""
    if not q:
        return JSONResponse([])
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    results = svc.search_all(q, top_k, mode=mode)
    return JSONResponse(results)


@router.get("/api/knowledge-bases/{kb_name}")
async def api_get_kb(request: Request, kb_name: str, page: int | None = None, page_size: int = 20):
    """获取知识库详情（含文档列表，支持分页）。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    if page is not None:
        result = svc.get_knowledge_base_paginated(kb_name, page, page_size)
    else:
        result = svc.get_knowledge_base(kb_name)
    if not result:
        return JSONResponse(status_code=404, content={"error": f"知识库 {kb_name} 不存在"})
    return JSONResponse(result)


@router.post("/api/knowledge-bases")
async def api_create_kb(request: Request):
    """创建知识库。"""
    ctx: AppContext = request.app.state.context
    body = await request.json()
    name = body.get("kb_name", "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "kb_name 不能为空"})
    svc = kb_service_for_context(ctx)
    result = svc.create_knowledge_base(name, body.get("description", ""))
    return JSONResponse(result)


@router.delete("/api/knowledge-bases/{kb_name}")
async def api_delete_kb(request: Request, kb_name: str):
    """删除知识库。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    ok = svc.delete_knowledge_base(kb_name)
    if not ok:
        return JSONResponse(status_code=404, content={"error": f"知识库 {kb_name} 删除失败"})
    return JSONResponse({"success": True})


@router.post("/api/knowledge-bases/batch-delete")
async def api_batch_delete_kbs(request: Request):
    """批量删除知识库。"""
    body = await request.json()
    names = body.get("names", [])
    if not names:
        return JSONResponse(status_code=400, content={"error": "names 不能为空"})
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    count = svc.delete_knowledge_bases_batch(names)
    return JSONResponse({"success": True, "deleted_count": count})


@router.post("/api/knowledge-bases/{kb_name}/rename")
async def api_rename_kb(request: Request, kb_name: str):
    """重命名知识库（可选同时更新描述）。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    body = await request.json()
    new_name = body.get("new_name", "").strip()
    description = body.get("description")

    if not new_name:
        return JSONResponse(status_code=400, content={"error": "new_name 不能为空"})

    result = svc.rename_knowledge_base(kb_name, new_name, description=description)
    if not result.get("success"):
        return JSONResponse(status_code=400, content=result)
    return JSONResponse(result)


@router.post("/api/knowledge-bases/{kb_name}/documents/{doc_id}/rename")
async def api_rename_document(request: Request, kb_name: str, doc_id: str):
    """重命名文档。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    body = await request.json()
    new_filename = body.get("new_filename", "").strip()
    if not new_filename:
        return JSONResponse(status_code=400, content={"error": "new_filename 不能为空"})
    result = svc.rename_document(doc_id, new_filename)
    return JSONResponse(result)


@router.post("/api/knowledge-bases/{kb_name}/ingest")
async def api_ingest_document(request: Request, kb_name: str):
    """导入文档到知识库（支持文件上传或路径）。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)

    body = await request.json()
    file_path = body.get("file_path", "").strip()
    text = body.get("text", "").strip()
    filename = body.get("filename", "inline.txt")

    if file_path:
        if not Path(file_path).exists():
            return JSONResponse(status_code=400, content={"error": f"文件不存在: {file_path}"})
        result = svc.ingest_file(kb_name, file_path)
    elif text:
        result = svc.ingest_text(kb_name, text, filename)
    else:
        return JSONResponse(status_code=400, content={"error": "请提供 file_path 或 text"})

    return JSONResponse(result)


@router.get("/api/knowledge-bases/{kb_name}/search")
async def api_search_kb(request: Request, kb_name: str, q: str = "", top_k: int = 5, mode: str = "vector"):
    """搜索知识库。mode: vector / fts。"""
    if not q:
        return JSONResponse([])
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    results = svc.search(kb_name, q, top_k, mode=mode)
    return JSONResponse(results)


@router.get("/api/knowledge-bases/{kb_name}/documents/{doc_id}")
async def api_get_document_detail(request: Request, kb_name: str, doc_id: str):
    """获取文档详情（含全文内容和分块列表）。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    result = svc.get_document_detail(kb_name, doc_id)
    if not result:
        return JSONResponse(status_code=404, content={"error": f"文档 {doc_id} 不存在"})
    return JSONResponse(result)


@router.delete("/api/knowledge-bases/{kb_name}/documents/{doc_id}")
async def api_delete_document(request: Request, kb_name: str, doc_id: str):
    """删除知识库中的单个文档。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    svc._repo.delete_document(doc_id)
    svc._vector.delete_document_chunks(kb_name, doc_id)
    svc._repo.update_kb_stats(kb_name)
    return JSONResponse({"success": True, "doc_id": doc_id})


@router.post("/api/knowledge-bases/{kb_name}/documents/batch-delete")
async def api_batch_delete_documents(request: Request, kb_name: str):
    """批量删除知识库中的文档。"""
    body = await request.json()
    doc_ids = body.get("doc_ids", [])
    if not doc_ids:
        return JSONResponse(status_code=400, content={"error": "doc_ids 不能为空"})
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)
    count = svc.delete_document_batch(doc_ids)
    # 删除向量数据
    for doc_id in doc_ids:
        try:
            svc._vector.delete_document_chunks(kb_name, doc_id)
        except Exception:
            pass
    svc._repo.update_kb_stats(kb_name)
    return JSONResponse({"success": True, "deleted_count": count})


@router.post("/api/knowledge-bases/{kb_name}/upload")
async def api_upload_document(request: Request, kb_name: str, file: UploadFile = File(...)):
    """上传文件到知识库（multipart）。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)

    content = await file.read()
    filename = file.filename or "uploaded.bin"
    result = svc.ingest_bytes(kb_name, filename, content)
    return JSONResponse(result)


# ── 模型管理 ─────────────────────────────────────────────────


@router.post("/api/rag/download-model")
async def api_download_rag_model(request: Request):
    """下载 BGE embedding 模型。"""
    try:
        BGEChineseEmbedding.download_model()
        return JSONResponse({"success": True, "message": "Embedding 模型下载完成"})
    except RuntimeError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/api/rag/reload-model")
async def api_reload_rag_model(request: Request):
    """从本地缓存重新加载 embedding 模型。"""
    try:
        BGEChineseEmbedding.load_local_model()
        return JSONResponse({"success": True, "message": "模型重新加载完成"})
    except RuntimeError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@router.get("/api/rag/model-status")
async def api_rag_model_status(request: Request):
    """查询 embedding 模型状态，未加载时尝试从本地缓存自动加载。"""
    if not BGEChineseEmbedding.is_ready():
        try:
            BGEChineseEmbedding.load_local_model()
        except Exception:
            pass  # 本地无缓存，保持未加载状态

    return JSONResponse({
        "ready": BGEChineseEmbedding.is_ready(),
        "model": BGEChineseEmbedding.MODEL_NAME,
        "dimension": BGEChineseEmbedding.MODEL_DIMENSION,
    })


@router.post("/api/rag/rebuild-indexes")
async def api_rebuild_indexes(request: Request):
    """重建所有知识库的向量索引（模型升级后使用）。"""
    ctx: AppContext = request.app.state.context
    svc = kb_service_for_context(ctx)

    if not BGEChineseEmbedding.is_ready():
        return JSONResponse(
            {"success": False, "error": "Embedding 模型未加载，请先下载模型"},
            status_code=400,
        )
    result = svc.rebuild_all_indexes()
    total = sum(result.values())
    return JSONResponse({"success": True, "rebuild": result, "total_chunks": total})
