"""情境闪现扫描器。

扫描低保留率 (retention < 0.3) 的记忆，当当前上下文与这些记忆
语义相似度 > 0.85 时，以 '[情境闪现] 你可能想起来了...' 前缀注入。
"""

from __future__ import annotations

import logging
from typing import Any

from domain.memory.entity import MemoryEntry
from infrastructure.persistence.memory_repo import MemoryRepository
from infrastructure.vector.chroma_store import ChromaStore

logger = logging.getLogger("sivan.flashback")

# 余弦相似度阈值（ChromaDB 返回 L2 distance，阈值映射：distance < 0.2 约等于 cosine > 0.85）
_SIMILARITY_THRESHOLD = 0.85
# L2 distance 对应阈值（cosine ≈ 1 - distance²/2，对于归一化向量）
_DISTANCE_THRESHOLD = 0.4
# 最大候选数
_MAX_CANDIDATES = 200
# 每次闪现最多注入条数
_MAX_FLASHBACKS = 3


class FlashbackScanner:
    """情境闪现扫描器。

    组合 MemoryRepository (SQL 查询低保留率记忆) + ChromaStore (向量相似度)，
    识别可能与当前上下文相关的已淡忘记忆。
    """

    def __init__(
        self,
        memory_repo: MemoryRepository,
        chroma_store: ChromaStore,
    ) -> None:
        self._repo = memory_repo
        self._chroma = chroma_store

    def scan(
        self,
        current_context: str,
        scope_ids: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """扫描低保留率记忆，返回与当前上下文语义匹配的结果。

        Args:
            current_context: 当前任务/对话文本
            scope_ids: 作用域过滤，如 {"level": "scope_id"}，用于限定扫描范围

        Returns:
            list[dict]: 每条包含 memory_id, content, retention, similarity
        """
        if not current_context or not current_context.strip():
            return []

        # 1. 从 ChromaDB 搜索语义相近的记忆（不限 retention）
        chroma_results = self._chroma.search(
            query=current_context,
            top_k=_MAX_CANDIDATES,
            **({"level": list(scope_ids.keys())[0]} if scope_ids and len(scope_ids) == 1 else {}),
        )

        if not chroma_results:
            return []

        # 2. 从 SQLite 批量查询这些 memory_id 的 retention 和 is_important 状态
        candidate_ids = [r["id"] for r in chroma_results if r.get("id")]
        if not candidate_ids:
            return []

        entries_map: dict[str, MemoryEntry] = {}
        try:
            entries = self._repo.find_by_ids(candidate_ids)
            for e in entries:
                entries_map[e.memory_id] = e
        except Exception:
            return []

        # 3. 筛选条件：低保留率 + 高相似度 + 非已归档 + 非重要（重要记忆已在正常上下文）
        flashbacks: list[dict[str, Any]] = []
        for r in chroma_results:
            mid = r.get("id", "")
            entry = entries_map.get(mid)
            if not entry:
                continue
            if entry.is_archived:
                continue
            if entry.retention >= 0.3:
                continue
            # 重要记忆不走闪现（它们保留率高，此处仅为防御）
            if entry.is_important:
                continue

            # 计算语义相似度（ChromaDB L2 distance → cosine similarity）
            distance = r.get("distance", 1.0)
            similarity = 1.0 - distance  # 对于近似归一化向量
            if similarity < _SIMILARITY_THRESHOLD:
                continue

            flashbacks.append({
                "memory_id": mid,
                "content": entry.content[:300],
                "retention": round(entry.retention, 4),
                "similarity": round(similarity, 4),
                "metadata": entry.metadata or {},
            })

        # 4. 按相似度排序，取 top N
        flashbacks.sort(key=lambda x: x["similarity"], reverse=True)
        return flashbacks[:_MAX_FLASHBACKS]

    def format_flashback(
        self,
        flashbacks: list[dict[str, Any]],
    ) -> str:
        """将闪现结果格式化为 system_prompt 注入文本。"""
        if not flashbacks:
            return ""

        lines = [
            "\n[情境闪现]",
            "--- 以下是你可能已经忘记但和当前任务相关的记忆，供参考 ---",
        ]
        for fb in flashbacks:
            content = fb.get("content", "")
            sim = fb.get("similarity", 0)
            ret = fb.get("retention", 0)
            lines.append(
                f"- (相似度: {sim:.2f}, 保留率: {ret:.2f}) {content}"
            )
        return "\n".join(lines)

    def confirm_flashback(
        self,
        memory_id: str,
    ) -> bool:
        """用户确认闪现有用 → 重置 retention=1.0。"""
        try:
            entry = self._repo.find_by_id(memory_id)
            if not entry:
                return False
            entry.retention = 1.0
            from datetime import datetime
            entry.last_accessed_at = datetime.now()
            entry.access_count += 1
            self._repo.update(entry)
            return True
        except Exception as e:
            logger.warning("确认闪现失败: %s", e)
            return False
