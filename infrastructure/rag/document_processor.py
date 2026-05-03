"""文档解析与分块。"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from domain.knowledge_base.entity import Chunk

logger = logging.getLogger("sivan.rag.processor")

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


class DocumentParser:
    """解析各种格式的文档，提取纯文本和元数据。"""

    @classmethod
    def read(cls, file_path: str | Path) -> tuple[str, dict[str, Any]]:
        """读取文档，返回 (full_text, metadata)。

        metadata 包含:
          - filename: 文件名
          - file_type: 扩展名（txt / md / pdf）
          - char_count: 字符数
          - headings: Markdown 标题列表（仅 md）
          - page_count: 页数（仅 pdf）
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {ext}，支持: {SUPPORTED_EXTENSIONS}")

        if ext == ".pdf":
            return cls._read_pdf(path)
        return cls._read_text(path)

    @classmethod
    def _read_text(cls, path: Path) -> tuple[str, dict]:
        text = path.read_text(encoding="utf-8")
        headings = cls._extract_headings(text) if path.suffix.lower() == ".md" else []
        meta = {
            "filename": path.name,
            "file_type": path.suffix[1:],
            "char_count": len(text),
            "headings": headings,
        }
        return text, meta

    @classmethod
    def _read_pdf(cls, path: Path) -> tuple[str, dict]:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            txt = (page.extract_text() or "").strip()
            if txt:
                pages.append(txt)
        text = "\n".join(pages)
        meta = {
            "filename": path.name,
            "file_type": "pdf",
            "char_count": len(text),
            "page_count": len(reader.pages),
        }
        return text, meta

    @classmethod
    def _extract_headings(cls, text: str) -> list[str]:
        """提取 Markdown 标题行。"""
        return [line.strip() for line in text.split("\n") if line.strip().startswith("#")]


class RecursiveChunkSplitter:
    """递归分块：段落 → 行 → 句 → 字符硬切，保留重叠。"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        if chunk_overlap >= chunk_size:
            chunk_overlap = chunk_size // 4
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(
        self,
        text: str,
        kb_name: str = "",
        doc_id: str = "",
        source: str = "",
        headings: list[str] | None = None,
    ) -> list[Chunk]:
        """将文本分块并返回 Chunk 列表。"""
        raw_chunks = self._split_recursive(
            text,
            [
                "\n\n",
                "\n",
                "。",
                "！",
                "？",
                ".!?",
                "；",
                "\r\n",
            ],
        )
        result: list[Chunk] = []
        heading_index = 0
        current_heading = headings[0] if headings else ""

        for i, chunk_text in enumerate(raw_chunks):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            # 跟踪最近的标题（仅 md）
            if headings and heading_index < len(headings):
                for h in headings[heading_index:]:
                    if h in chunk_text:
                        current_heading = h
                        heading_index += 1

            result.append(
                Chunk(
                    chunk_id=uuid.uuid4().hex,
                    kb_name=kb_name,
                    doc_id=doc_id,
                    text=chunk_text,
                    chunk_index=i,
                    heading=current_heading,
                    source=source,
                )
            )

        return result

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        """递归分割，按分隔符优先级逐级拆分。"""
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            return self._hard_split(text)

        sep = separators[0]
        rest = separators[1:]

        segments = text.split(sep)
        chunks: list[str] = []
        buffer = ""

        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue

            candidate = (buffer + sep + seg) if buffer else seg

            if len(candidate) <= self.chunk_size:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer)
                # 当前段仍超长，递归
                if len(seg) > self.chunk_size:
                    sub = self._split_recursive(seg, rest)
                    chunks.extend(sub)
                else:
                    buffer = seg

        if buffer:
            chunks.append(buffer)

        # 应用重叠
        return self._apply_overlap(chunks)

    def _hard_split(self, text: str) -> list[str]:
        """字符级硬切。"""
        return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        """给相邻 chunk 追加重叠字符。"""
        if len(chunks) <= 1 or self.chunk_overlap <= 0:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            overlap = prev[-self.chunk_overlap :] if len(prev) > self.chunk_overlap else prev
            result.append(overlap + chunks[i])
        return result
