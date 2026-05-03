"""智能体值对象。

定义 Capability、SkillRef、ToolPermission 等不可变值对象。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    """智能体能力描述值对象。"""
    name: str
    description: str
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillRef:
    """技能引用值对象。"""
    skill_id: str
    name: str
    category: str = ""


@dataclass(frozen=True)
class ToolPermission:
    """工具权限值对象。"""
    tool_name: str
    allow: bool = True
    restricted: bool = False
