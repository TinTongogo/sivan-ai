"""管理控制台共享上下文。

提供 AppContext 单例，集中管理 db_path、jinja_env、模板过滤器，
配置项统一从 config/settings.py 读取。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from config.settings import settings

# ── 项目路径 ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent


# ── Jinja2 过滤器 ───────────────────────────────────────────────


def format_number_filter(num):
    """格式化数字显示 (K/M 单位)"""
    if num is None:
        return "0"
    try:
        num = float(num)
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num / 1_000:.1f}K"
        else:
            return str(int(num))
    except (ValueError, TypeError):
        return str(num)


def format_date_filter(date_str):
    """格式化日期显示"""
    try:
        if not date_str:
            return ""
        if "T" in date_str:
            from datetime import datetime

            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            from datetime import datetime

            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return date_str


def get_chart_color_filter(index, hover=False):
    """获取图表颜色 - 用于Jinja2模板"""
    colors = [
        "#4e73df",
        "#1cc88a",
        "#36b9cc",
        "#f6c23e",
        "#858796",
        "#e74a3b",
        "#fd7e14",
        "#20c9a6",
        "#6610f2",
        "#6f42c1",
    ]
    hover_colors = [
        "#2e59d9",
        "#17a673",
        "#2c9faf",
        "#dda20a",
        "#6c757d",
        "#be2617",
        "#dc6502",
        "#18a18e",
        "#560bd1",
        "#5a32a3",
    ]
    color_array = hover_colors if hover else colors
    return color_array[index % len(color_array)]


# ── AppContext 单例 ─────────────────────────────────────────────


class AppContext:
    """管理控制台共享上下文。

    在 admin.py 启动时创建，被 routes/ 下各模块用于获取
    jinja_env 进行模板渲染，以及获取 db_path 传给 services。
    """

    def __init__(self) -> None:
        self.db_path: Path = Path(settings.DB_PATH)
        self._start_time = time.time()

        templates_dir = PROJECT_ROOT / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
            auto_reload=True,
        )
        self.jinja_env.filters["format_number"] = format_number_filter
        self.jinja_env.filters["format_date"] = format_date_filter
        self.jinja_env.filters["get_chart_color"] = get_chart_color_filter

        # KB service（轻量初始化，不依赖 LLM providers）
        self._kb_service: Any = None

    @property
    def kb_service(self) -> Any:
        """延迟初始化 KnowledgeBaseService 并缓存。"""
        if self._kb_service is None:
            from application.services.kb_service import KnowledgeBaseService
            from infrastructure.persistence.connection import SQLiteConnectionManager
            from infrastructure.persistence.kb_repo import KnowledgeBaseRepository
            from infrastructure.rag.embedding import BGEChineseEmbedding
            from infrastructure.vector.kb_chroma_store import KnowledgeBaseChromaStore

            vector_store = KnowledgeBaseChromaStore(
                persist_dir=settings.CHROMA_PATH,
                embedding_function=BGEChineseEmbedding(),
            )
            conn_mgr = SQLiteConnectionManager(str(self.db_path))
            kb_repo = KnowledgeBaseRepository(conn_mgr, vector_store)
            # 从 DB 读取 RAG 配置（不存在则用默认值）
            from interfaces.api.services.settings import get_config as _get_cfg

            _cs = int(_get_cfg(str(self.db_path), "rag_chunk_size") or "500")
            _co = int(_get_cfg(str(self.db_path), "rag_chunk_overlap") or "50")
            svc = KnowledgeBaseService(kb_repo, vector_store, chunk_size=_cs, chunk_overlap=_co)
            self._kb_service = svc
        return self._kb_service

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self._start_time)
