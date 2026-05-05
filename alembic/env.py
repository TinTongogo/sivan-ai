"""Alembic 迁移环境配置。

使用 infrastructure.persistence.models.metadata 作为 target_metadata，
确保迁移自动跟踪所有 SQLAlchemy Core 表定义。
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── 关键：引入 models 模块以注册所有表到 metadata ──
from infrastructure.persistence.models import metadata

target_metadata = metadata


def include_object(obj: Any, name: str, type_: str,
                   reflected: bool, compare_to: Any) -> bool:
    """排除 FTS5 内部表（由 kb_repo.py 手动管理）。"""
    if type_ == "table" and name.startswith("kb_documents_fts"):
        return False
    return True


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：直接连接数据库执行迁移。"""
    # 从环境变量获取 DB 路径
    from pathlib import Path

    from config.settings import settings

    db_path = os.getenv("SIVAN_DB_PATH", str(settings.DB_PATH))
    db_url = f"sqlite:///{db_path}"

    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = db_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
