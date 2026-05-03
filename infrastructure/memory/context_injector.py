"""记忆上下文注入逻辑。

当 Agent 执行任务时，从记忆库检索相关记忆并注入到 system_prompt。
集成情境闪现（FlashbackScanner），检索被遗忘但相关的记忆。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from config.settings import settings
from domain.common.interfaces import IContextInjector
from domain.common.value_object import MemoryLevel
from domain.memory.entity import MemoryEntry
from domain.memory.value_object import MemoryQuery


class ContextInjector(IContextInjector):
    """记忆上下文注入器。

    职责：
    1. 基于当前上下文检索相关记忆
    2. 按遗忘曲线保留率过滤 (R > threshold)
    3. 格式化为 system_prompt 附加段
    4. 集成情境闪现，找回已被遗忘但相关的记忆

    配置读取优先级：构造函数参数 > DB > settings.py env var 默认值。
    """

    def __init__(
        self,
        search_fn: Callable[[MemoryQuery], list[MemoryEntry]],
        min_retention: float | None = None,
        max_memories: int | None = None,
        flashback_scanner: Any | None = None,
    ) -> None:
        self._search_fn = search_fn
        self.MIN_RETENTION = (
            min_retention
            if min_retention is not None
            else settings.MEMORY_DEFAULT_MIN_RETENTION
        )
        self.MAX_MEMORIES = (
            max_memories
            if max_memories is not None
            else settings.MEMORY_MAX_CONTEXT_MEMORIES
        )
        self._flashback_scanner = flashback_scanner

    def build_context(
        self,
        query: str,
        scope_ids: dict[MemoryLevel, str] | None = None,
        top_k: int = 5,
    ) -> str:
        """构建记忆上下文文本，供注入 system_prompt。

        Args:
            query: 当前任务描述
            scope_ids: 各层级的 scope_id，如 {MemoryLevel.TEAM: "team-1", ...}
            top_k: 每层最多取几条

        Returns:
            str: 格式化的记忆上下文文本，无相关内容时返回空字符串
        """
        if scope_ids is None:
            scope_ids = {}

        all_memories: list[dict[str, Any]] = []

        # 从各层级检索记忆
        for level, scope_id in scope_ids.items():
            memory_query = MemoryQuery(
                query_text=query,
                level=level,
                scope_id=scope_id,
                limit=top_k,
                min_retention=self.MIN_RETENTION,
            )
            entries = self._search_fn(memory_query)
            for entry in entries:
                all_memories.append({
                    "level": level.value,
                    "content": entry.content,
                    "retention": entry.retention,
                    "access_count": entry.access_count,
                })

        parts: list[str] = []

        # 正常记忆上下文
        if all_memories:
            all_memories.sort(key=lambda x: x["retention"], reverse=True)
            all_memories = all_memories[:self.MAX_MEMORIES]

            lines = ["\n[相关记忆]", f"--- 检索到 {len(all_memories)} 条相关记忆 ---"]
            for m in all_memories:
                level_label = f"[{m['level']}]"
                retention_label = f"(保留率: {m['retention']:.2f})"
                lines.append(f"{level_label} {m['content'][:200]} {retention_label}")
            parts.append("\n".join(lines))

        # 情境闪现：低保留率但语义相似的高价值记忆
        if self._flashback_scanner:
            try:
                # 将 scope_ids 转为 {level: scope_id} 格式
                scope_lookup = {lv.value: sid for lv, sid in scope_ids.items()}
                flashbacks = self._flashback_scanner.scan(query, scope_lookup)
                if flashbacks:
                    flashback_text = self._flashback_scanner.format_flashback(flashbacks)
                    if flashback_text:
                        parts.append(flashback_text)
            except Exception:
                pass

        return "\n".join(parts)

    def inject_to_prompt(
        self,
        system_prompt: str,
        memory_context: str,
    ) -> str:
        """将记忆上下文注入到 system_prompt。

        如果已有 [相关记忆] 或 [情境闪现] 段则替换，否则追加到末尾。
        """
        if not memory_context:
            return system_prompt

        marker = "\n[相关记忆]"
        marker2 = "\n[情境闪现]"
        if marker in system_prompt:
            before = system_prompt.split(marker)[0]
            return before + memory_context
        if marker2 in system_prompt:
            before = system_prompt.split(marker2)[0]
            return before + memory_context
        return system_prompt + memory_context
