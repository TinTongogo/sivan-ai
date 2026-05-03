"""知识库 API 服务辅助。"""

from __future__ import annotations

from interfaces.api.context import AppContext


def kb_service_for_context(ctx: AppContext) -> ...:
    """从 AppContext 获取 KnowledgeBaseService 单例。"""
    return ctx.kb_service
