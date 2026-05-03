"""统一日志配置。

使用 loguru 替代零散 logging/print，支持控制台、文件、DB 三路输出。
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: str | Path = "data/logs", level: str = "DEBUG") -> None:
    """初始化 loguru 日志。

    控制台输出彩色日志，文件按天轮转保留 30 天。
    """
    logger.remove()

    # 控制台
    logger.add(
        sys.stderr,
        format="<green>{time:MM-DD HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}:{line}</cyan> | <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # 文件
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_path / "sivan_{time:YYYY-MM-DD}.log"),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {name}:{line} | {message}",
        rotation="1 day",
        retention="30 days",
        level=level,
        compression="gz",
    )
