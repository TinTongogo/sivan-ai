"""知识库值对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeBaseQuery:
    """知识库检索查询。"""

    query_text: str
    kb_name: str | None = None  # None = 搜索所有 KB
    top_k: int = 5
    min_score: float = 0.0


@dataclass
class SearchResult:
    """检索结果条目。"""

    chunk_id: str
    kb_name: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
