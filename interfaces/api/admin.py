"""管理控制台入口 (DDD 架构版)。"""

from __future__ import annotations

import hashlib
import logging
import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from interfaces.api.context import (
    PROJECT_ROOT,
    AppContext,
)

SIVAN_API_KEY = settings.SIVAN_API_KEY
AUTH_COOKIE_NAME = settings.AUTH_COOKIE_NAME
AUTH_COOKIE_MAX_AGE = settings.AUTH_COOKIE_MAX_AGE
from interfaces.api.routes import (
    agents,
    contracts,
    conversations,
    dashboard,
    knowledge_base,
    logs,
    memory,
    projects,
    reports,
    routing,
    skills,
    squads,
    tokens,
)
from interfaces.api.routes import settings as settings_routes

# 确保项目根目录在路径中
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── 创建共享上下文 ────────────────────────────────────────────

_context: AppContext = AppContext()


def get_context() -> AppContext:
    return _context


# ── 创建 FastAPI 应用 ─────────────────────────────────────────
logger = logging.getLogger("sivan.admin")
app = FastAPI(title="Sivan 管理控制台", version="1.0.0")
app.state.context = _context

# 静态文件
static_dir = PROJECT_ROOT / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── 注册路由模块 ──────────────────────────────────────────────

app.include_router(dashboard.router)
app.include_router(agents.router)
app.include_router(contracts.router)
app.include_router(tokens.router)
app.include_router(routing.router)
app.include_router(skills.router)
app.include_router(squads.router)
app.include_router(reports.router)
app.include_router(memory.router)
app.include_router(logs.router)
app.include_router(conversations.router)
app.include_router(knowledge_base.router)
app.include_router(projects.router)
app.include_router(settings_routes.router)


# ── 认证中间件 ────────────────────────────────────────────────


def _hash_token(token: str) -> str:
    return hashlib.sha256((token + settings.AUTH_SALT).encode()).hexdigest()


def _verify_auth(request: Request) -> bool:
    if not SIVAN_API_KEY:
        return True
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token and token == _hash_token(SIVAN_API_KEY):
        return True
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:] == SIVAN_API_KEY:
        return True
    return False


if SIVAN_API_KEY:
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if request.url.path in ("/login", "/favicon.svg") or \
           request.url.path.startswith("/static") or \
           request.url.path.startswith("/mcp"):
            return await call_next(request)
        if not _verify_auth(request):
            if request.url.path.startswith("/api/"):
                return JSONResponse(status_code=401, content={"error": "未授权，请提供有效的 API Key"})
            return RedirectResponse(url="/login", status_code=303)
        return await call_next(request)


# ── MCP 服务集成（生命周期管理 + 挂载） ──────────────────────────

try:
    from interfaces.mcp.server import app as _mcp_app
    from interfaces.mcp.server import MCPAuthMiddleware

    _mcp_http = _mcp_app.http_app(transport="http", stateless_http=True)
    if settings.MCP_API_KEY:
        _mcp_http.add_middleware(MCPAuthMiddleware)
    app.mount("/mcp", _mcp_http)
    app.router.lifespan_context = _mcp_http.lifespan
    _HAS_MCP = True
except Exception as e:
    print(f"⚠️  MCP 集成失败: {e}")
    _HAS_MCP = False


# ── 登录/登出路由 ─────────────────────────────────────────────


@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import FileResponse
    return FileResponse(str(PROJECT_ROOT / "static" / "favicon.svg"), media_type="image/svg+xml")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if not SIVAN_API_KEY:
        return RedirectResponse(url="/")
    template = _context.jinja_env.get_template("login.html")
    return HTMLResponse(content=template.render(request=request, error=error))


@app.post("/login")
async def login_submit(request: Request):
    if not SIVAN_API_KEY:
        return RedirectResponse(url="/")
    form = await request.form()
    if form.get("api_key") == SIVAN_API_KEY:
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=_hash_token(SIVAN_API_KEY),
            max_age=AUTH_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
        return resp
    return RedirectResponse(url="/login?error=1", status_code=303)


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login")
    resp.delete_cookie(AUTH_COOKIE_NAME)
    return resp


# ── 初始化数据库 ──────────────────────────────────────────────


def init_database():
    """初始化数据库表结构（由 Alembic 管理）+ 种子数据。"""
    from interfaces.api.services import check_and_generate_weekly_report, check_skill_archiving

    db_path = _context.db_path

    # 用 SQLAlchemy metadata 直接建表
    try:
        from infrastructure.persistence.database import init_engine
        from infrastructure.persistence.models import metadata

        engine = init_engine(db_path)
        metadata.create_all(engine)
        print("✅ 所有数据库表初始化完成")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

    # 恢复上次异常中断的消息（pending/running → failed）
    try:
        from interfaces.api.services.conversations import recover_stuck_messages
        stuck = recover_stuck_messages(db_path)
        if stuck:
            print(f"✅ 已恢复 {stuck} 条卡住的消息")
    except Exception as e:
        print(f"⚠️ 消息恢复失败: {e}")

    # 技能归档检查
    try:
        check_skill_archiving(db_path)
    except Exception as e:
        print(f"⚠️ 技能归档检查失败: {e}")

    # 周报自动生成检查
    try:
        check_and_generate_weekly_report(db_path)
    except Exception as e:
        print(f"⚠️ 周报自动生成检查失败: {e}")

    # 默认配置 seed
    try:
        from interfaces.api.services.settings import init_default_settings
        init_default_settings(db_path)
        print("✅ 默认配置已初始化")
    except Exception as e:
        print(f"❌ 默认配置初始化失败: {e}")

    # 初始化默认项目
    try:
        from interfaces.api.services.settings import init_default_project
        init_default_project(db_path)
    except Exception as e:
        print(f"❌ 默认项目初始化失败: {e}")

    # 迁移旧 auth_type 值到新命名（bearer → OpenAI, x-api-key → Anthropic, none → OpenAI）
    try:
        c = __import__("sqlite3").connect(str(db_path))
        cur = c.cursor()
        cur.execute("UPDATE llm_providers SET auth_type = 'OpenAI' WHERE auth_type IN ('bearer', 'none')")
        cur.execute("UPDATE llm_providers SET auth_type = 'Anthropic' WHERE auth_type = 'x-api-key'")
        c.commit()
        c.close()
    except Exception as e:
        print(f"❌ auth_type 迁移失败: {e}")


# ── 启动 ──────────────────────────────────────────────────────


def main():
    """启动管理控制台。"""
    from infrastructure.logging.setup import setup_logging
    setup_logging(str(PROJECT_ROOT / "data" / "logs"))
    init_database()
    from infrastructure.logging.db_logger import init_db_logger
    init_db_logger(str(PROJECT_ROOT / "data" / "sivan.db"))

    host = settings.ADMIN_HOST
    port = settings.ADMIN_PORT
    print("🚀 Sivan 管理控制台启动中...")
    print(f"📊 访问地址: http://{host}:{port}")
    print("📊 系统统计: /api/stats")
    print("👥 智能体管理: /agents")
    print("📝 契约管理: /contracts")
    print("💰 Token统计: /tokens")
    print("🔄 路由分析: /routing")
    print("🔧 技能管理: /skills")
    print("👥 Squad管理: /squads")
    print("📊 周报管理: /reports")
    print("⚙️ 系统设置: /settings")
    if _HAS_MCP:
        print("🔌 MCP HTTP: /mcp/mcp")
    print("\n按 Ctrl+C 停止服务器")

    import asyncio

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        ws_ping_interval=30,
        ws_ping_timeout=10,
    )
    server = uvicorn.Server(config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    except KeyboardInterrupt:
        loop.run_until_complete(server.shutdown())
    finally:
        loop.close()
