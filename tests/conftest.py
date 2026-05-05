"""pytest 共享 fixtures。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Iterator

import pytest
from sqlalchemy import inspect as sa_inspect

from config.settings import Settings

# ── 测试数据库路径 ──────────────────────────────────────────────
# 在 infrastructure.persistence.database 被导入前确定

_TEST_DB: str = ""


@pytest.fixture(scope="session", autouse=True)
def _setup_test_env() -> Iterator[None]:
    """创建临时数据库目录，供整个测试会话使用。"""
    tmpdir = tempfile.mkdtemp(prefix="sivan_test_")
    db_path = Path(tmpdir) / "test.db"
    global _TEST_DB
    _TEST_DB = str(db_path)

    # 覆盖 DB_PATH 环境变量
    os.environ["SIVAN_DB_PATH"] = _TEST_DB
    # 禁用认证（测试用）
    os.environ.setdefault("SIVAN_API_KEY", "test-key")

    from sqlalchemy import MetaData, create_engine
    from infrastructure.persistence.models import metadata

    # 直接建表（等价于 alembic upgrade head）
    engine = create_engine(f"sqlite:///{_TEST_DB}", echo=False)
    metadata.create_all(engine)
    engine.dispose()

    yield

    # 清理
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    """每次测试前清空所有表（保留结构）。"""
    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{_TEST_DB}", echo=False)
    table_names = sa_inspect(engine).get_table_names()
    with engine.connect() as conn:
        for table in reversed(table_names):
            conn.execute(text(f"DELETE FROM {table}"))
        conn.commit()
    engine.dispose()

    yield


@pytest.fixture
def db_path() -> str:
    return _TEST_DB


@pytest.fixture
def sample_agents() -> dict[str, list[str]]:
    return {
        "be-dev": ["后端开发", "API设计", "数据库设计", "微服务架构"],
        "fe-dev": ["前端开发", "UI组件", "响应式设计", "状态管理"],
        "qa": ["测试用例", "自动化测试", "性能测试", "回归测试"],
        "devops": ["CI/CD", "Docker", "Kubernetes", "监控告警"],
        "architect": ["系统架构", "技术选型", "高可用设计", "DDD建模"],
        "po": ["需求分析", "用户故事", "产品规划", "优先级管理"],
        "ui-ux": ["UI设计", "用户体验", "交互设计", "视觉设计"],
        "security-auditor": ["安全审计", "渗透测试", "威胁建模", "安全加固"],
        "data-engineer": ["数据管道", "ETL", "数据仓库", "数据分析"],
    }


@pytest.fixture
def routing_service(sample_agents: dict[str, list[str]]) -> Any:
    """创建配置好的路由应用服务（使用内存数据，不依赖 DB）。"""
    from domain.routing.strategy import (
        AdaptiveRouter,
        ContextAwareRouter,
        MLRouter,
        SemanticRouter,
    )
    from domain.routing.service import RoutingService as DomainRoutingService

    domain = DomainRoutingService(strategies={}, default_strategy="adaptive")

    # 注册 3 个子策略
    semantic = SemanticRouter()
    context = ContextAwareRouter()
    ml = MLRouter()

    domain.register_strategy("semantic", semantic)
    domain.register_strategy("context_aware", context)
    domain.register_strategy("ml", ml)

    adaptive = AdaptiveRouter(strategies={
        "semantic": semantic,
        "context_aware": context,
        "ml": ml,
    })
    domain.register_strategy("adaptive", adaptive)
    domain.switch_strategy("adaptive")

    for name, caps in sample_agents.items():
        domain.add_agent(name, caps)

    return domain
