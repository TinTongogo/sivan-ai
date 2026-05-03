"""应用配置管理。

从环境变量读取配置，提供统一的配置入口。
在 huggingface_hub / sentence-transformers 导入前设置 HF_ENDPOINT。
模型下载优先使用魔搭社区（modelscope），回退到 HuggingFace 镜像站。
"""

from __future__ import annotations

import os
from pathlib import Path

# ── HuggingFace 镜像站加速（魔搭回退） ──────────────────────
# 在 huggingface_hub 导入前设好环境变量，模型下载走镜像站
HF_ENDPOINT = os.environ.get("HF_ENDPOINT") or os.environ.get("SIVAN_HF_MIRROR", "https://hf-mirror.com")
os.environ.setdefault("HF_ENDPOINT", HF_ENDPOINT)
# ─────────────────────────────────────────────────────────────


class Settings:
    """应用配置。"""

    # 项目路径
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"

    # 数据库
    DB_PATH: str = os.getenv("SIVAN_DB_PATH", str(DATA_DIR / "sivan.db"))

    # ChromaDB 持久化路径
    CHROMA_PATH: str = os.getenv("SIVAN_CHROMA_PATH", str(DATA_DIR / "chroma"))

    # HuggingFace 镜像站（HF 下载回退用）
    HF_ENDPOINT: str = HF_ENDPOINT

    # ModelScope 缓存路径（默认 ~/.cache/modelscope）
    MODELSCOPE_CACHE: str = os.getenv("MODELSCOPE_CACHE", str(DATA_DIR / "modelscope"))

    # 认证
    SIVAN_API_KEY: str = os.getenv("SIVAN_API_KEY", "")  # 管理控制台
    MCP_API_KEY: str = os.getenv("MCP_API_KEY", "")  # MCP 服务器
    AUTH_COOKIE_NAME: str = "sivan_token"
    AUTH_COOKIE_MAX_AGE: int = 86400  # 24小时
    AUTH_SALT: str = "@sivan"

    # SMTP 邮件配置
    SMTP_HOST: str = os.getenv("SIVAN_SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SIVAN_SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SIVAN_SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SIVAN_SMTP_PASSWORD", "")
    SMTP_FROM_ADDRESS: str = os.getenv("SIVAN_SMTP_FROM", "noreply@sivan.local")

    # 记忆系统配置
    MEMORY_SESSION_TTL: int = 3600  # 会话记忆 TTL (秒)
    MEMORY_SESSION_MAX_SIZE: int = 1000  # 会话记忆最大条数
    MEMORY_DEFAULT_MIN_RETENTION: float = 0.3  # 检索最低保留率
    MEMORY_ARCHIVE_THRESHOLD: float = 0.15  # 归档阈值
    MEMORY_MAX_CONTEXT_MEMORIES: int = 10  # 上下文注入最大条数

    # 管理控制台
    ADMIN_HOST: str = os.getenv("SIVAN_ADMIN_HOST", "127.0.0.1")
    ADMIN_PORT: int = int(os.getenv("SIVAN_ADMIN_PORT", "8001"))

    # 项目隔离
    DEFAULT_PROJECT_ID: str = "default"


settings = Settings()
