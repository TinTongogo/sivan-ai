"""Ebbinghaus 遗忘曲线计算。

实现 R = e^(-t/S) 遗忘曲线，用于记忆保留率计算。
"""

from __future__ import annotations

import math
from datetime import datetime


def calculate_retention(
    last_accessed_at: datetime,
    stability_hours: float,
    access_count: int = 1,
    stability_multiplier: float = 1.0,
    now: datetime | None = None,
) -> float:
    """计算记忆保留率。

    使用 Ebbinghaus 遗忘曲线：
        R = e^(-t/(S * M)) * A

    其中：
    - t: 距上次访问的时间 (小时)
    - S: 记忆稳定性 (小时)，取决于层级
    - M: 稳定性乘数（is_important=重要记忆时 ×10）
    - A: 访问增强因子 = min(1.5, (access_count+1)^0.1)
      高频访问减缓衰减速度

    Args:
        last_accessed_at: 上次访问时间
        stability_hours: 记忆稳定性 (小时)
        access_count: 历史访问次数
        stability_multiplier: 稳定性乘数 (默认 1.0，重要记忆时 ×10)
        now: 当前时间

    Returns:
        float: 0.0 ~ 1.0 的保留率
    """
    if now is None:
        now = datetime.now()

    elapsed_hours = (now - last_accessed_at).total_seconds() / 3600.0
    if elapsed_hours < 0:
        elapsed_hours = 0.0
    if stability_hours <= 0:
        stability_hours = 1.0
    if stability_multiplier <= 0:
        stability_multiplier = 1.0

    # Access boost: 高频访问减缓衰减, access_count=1 时无增强
    access_boost = min(1.5, math.pow(max(access_count, 1), 0.1))

    retention = math.exp(-elapsed_hours / (stability_hours * stability_multiplier)) * access_boost
    return max(0.0, min(1.0, retention))


def time_until_retention_threshold(
    stability_hours: float,
    access_count: int = 1,
    stability_multiplier: float = 1.0,
    threshold: float = 0.3,
) -> float:
    """预测保留率降至阈值所需时间 (小时)。

    Args:
        stability_hours: 记忆稳定性 (小时)
        access_count: 历史访问次数
        stability_multiplier: 稳定性乘数
        threshold: 保留率阈值 (默认 0.3)

    Returns:
        float: 小时数
    """
    access_boost = min(1.5, math.pow(access_count + 1, 0.1))
    effective_stability = stability_hours * stability_multiplier * math.log(access_boost / threshold)
    return max(0.0, effective_stability)


def get_retention_level(retention: float) -> str:
    """获取保留率级别描述。"""
    if retention >= 0.8:
        return "vivid"
    if retention >= 0.5:
        return "clear"
    if retention >= 0.3:
        return "fading"
    if retention >= 0.15:
        return "dim"
    return "archived"
