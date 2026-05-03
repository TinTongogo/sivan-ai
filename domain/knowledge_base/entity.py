"""知识库领域实体。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class KnowledgeBase:
    """知识库。每个 KB 对应一个 ChromaDB collection。"""

    kb_name: str
    description: str = ""
    document_count: int = 0
    chunk_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Document:
    """已入库的源文档。"""

    doc_id: str
    kb_name: str
    filename: str
    source_path: str
    file_type: str  # txt | md | pdf
    chunk_count: int = 0
    char_count: int = 0
    text_content: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Chunk:
    """文档分块，含来源元数据。"""

    chunk_id: str
    kb_name: str
    doc_id: str
    text: str
    chunk_index: int
    heading: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
