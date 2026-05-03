"""领域层通用值对象。

不可变值对象：枚举、时间范围、分页请求等。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class MemoryLevel(Enum):
    """4 级记忆层次。"""

    SESSION = "session"
    USER = "user"
    TEAM = "team"
    PROJECT = "project"

    @property
    def stability_hours(self) -> float:
        """记忆稳定性 (小时)，用于遗忘曲线 R = e^(-t/S)。"""
        return {
            MemoryLevel.SESSION: 1.0,
            MemoryLevel.USER: 24.0,
            MemoryLevel.TEAM: 168.0,  # 7 days
            MemoryLevel.PROJECT: 720.0,  # 30 days
        }[self]

    @property
    def persistence(self) -> str:
        return {
            MemoryLevel.SESSION: "ephemeral",
            MemoryLevel.USER: "long_term",
            MemoryLevel.TEAM: "permanent",
            MemoryLevel.PROJECT: "permanent",
        }[self]

    @property
    def use_vector(self) -> bool:
        """是否需要向量存储。"""
        return self in (MemoryLevel.TEAM, MemoryLevel.PROJECT)


@dataclass(frozen=True)
class TimeRange:
    """时间范围值对象。"""
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("end must be after start")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def contains(self, dt: datetime) -> bool:
        return self.start <= dt <= self.end


@dataclass(frozen=True)
class PageRequest:
    """分页请求值对象。"""
    page: int = 1
    size: int = 20
    sort_by: str | None = None
    sort_desc: bool = True

    def __post_init__(self) -> None:
        if self.page < 1:
            object.__setattr__(self, "page", 1)
        if self.size < 1:
            object.__setattr__(self, "size", 20)
        if self.size > 100:
            object.__setattr__(self, "size", 100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size
