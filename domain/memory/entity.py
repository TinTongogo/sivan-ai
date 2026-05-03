"""记忆领域实体。

定义 MemoryEntry 为核心实体，包含遗忘曲线支持的生命周期管理。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.value_object import MemoryLevel


@dataclass
class MemoryEntry:
    """记忆条目实体。

    每个条目属于一个记忆层级 (session/user/team/project)，
    支持 Ebbinghaus 遗忘曲线计算和访问追踪。

    is_important: 标记为重要后稳定性系数 ×10（情感权重增强）。
    """

    memory_id: str
    level: MemoryLevel
    scope_id: str  # project_id, team_id, user_id 或 session_id
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    retention: float = 1.0
    is_archived: bool = False
    is_important: bool = False
    summary: str | None = None  # 归档后的摘要

    def calculate_retention(self, now: datetime | None = None) -> float:
        """计算当前保留率 (Ebbinghaus 遗忘曲线)。

        R = e^(-t / S)

        其中：
        - t = 距上次访问的时间 (小时)
        - S = 记忆稳定性 (小时，取决于层级)
        - 每次访问重置 t=0 (retrieval strengthens memory)
        - is_important=True 时稳定性系数 ×10
        """
        if now is None:
            now = datetime.now()
        elapsed_hours = (now - self.last_accessed_at).total_seconds() / 3600.0
        if elapsed_hours < 0:
            elapsed_hours = 0.0

        S = self.level.stability_hours
        # stability_multiplier: is_important 时 ×10
        stability_multiplier = 10.0 if self.is_important else 1.0
        # access_boost: 高频访问减缓衰减, access_count=0/1 时无增强
        access_boost = min(1.5, math.pow(max(self.access_count, 1), 0.1))
        self.retention = math.exp(-elapsed_hours / (S * stability_multiplier)) * access_boost
        self.retention = max(0.0, min(1.0, self.retention))
        return self.retention

    def access(self, now: datetime | None = None) -> None:
        """记录一次访问，重置衰减计时器。"""
        if now is None:
            now = datetime.now()
        self.last_accessed_at = now
        self.access_count += 1
        self.retention = 1.0

    def should_archive(self, now: datetime | None = None) -> bool:
        """是否应归档 (保留率低于 0.15)。"""
        return self.calculate_retention(now) < 0.15

    def should_summarize(self, now: datetime | None = None) -> bool:
        """是否需要压缩摘要 (保留率低于 0.25)。"""
        return self.calculate_retention(now) < 0.25
