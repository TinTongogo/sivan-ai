"""Embedding 函数：BGE 中文模型，sentence-transformers 必需。"""

from __future__ import annotations

import logging
from typing import Any

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger("sivan.rag.embedding")


class BGEChineseEmbedding(EmbeddingFunction):
    """基于 BGE 的中文 Embedding 函数。

    默认模型: BAAI/bge-small-zh-v1.5 (384 维，中文优化，约 30MB)。
    使用 sentence-transformers 加载，自动从 HuggingFace 下载。
    HF_ENDPOINT 镜像站配置已在 config/settings.py 中设置。

    模型必需预先下载（通过 download_model()），否则 __call__ 将抛出 RuntimeError。
    """

    MODEL_NAME = "BAAI/bge-small-zh-v1.5"
    MODEL_DIMENSION = 384

    _global_model: Any = None
    _global_available = False
    _global_model_path: str | None = None  # 实际使用的模型路径（ModelScope 本地缓存或 HF 模型名）

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or self.MODEL_NAME
        if not self._global_available or self._model_name != getattr(self._global_model, "_model_name", None):
            self._try_load()

    @classmethod
    def download_model(cls, model_name: str | None = None) -> None:
        """下载 BGE 模型。优先使用魔搭社区，失败后回退到 HuggingFace。同步阻塞，可能耗时。

        Raises:
            RuntimeError: 下载失败时抛出
        """
        name = model_name or cls.MODEL_NAME
        logger.info("正在下载 embedding 模型: %s ...", name)

        model_path = cls._try_modelscope_download(name)
        if model_path is None:
            model_path = name  # 回退到 HuggingFace（走 HF_ENDPOINT 镜像）
        cls._global_model_path = model_path

        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_path, trust_remote_code=True)
            # 触发实际编码以完成加载
            model.encode(["test"], show_progress_bar=False)
            cls._global_model = model
            cls._global_available = True
            cls._global_model._model_name = name
            dim = (
                model.get_embedding_dimension()
                if hasattr(model, "get_embedding_dimension")
                else model.get_sentence_embedding_dimension()
            )
            logger.info("BGE embedding 模型加载完成: %s (dim=%d)", name, dim)
        except Exception as exc:
            cls._global_available = False
            raise RuntimeError(f"Embedding 模型加载失败: {exc}") from exc

    @staticmethod
    def _try_modelscope_download(model_id: str) -> str | None:
        """尝试从魔搭社区下载模型，返回本地路径；失败返回 None。"""
        try:
            from modelscope.hub.snapshot_download import snapshot_download
        except ImportError:
            logger.info("modelscope 未安装，跳过魔搭下载")
            return None

        try:
            from config.settings import settings

            cache_dir = settings.MODELSCOPE_CACHE
            model_dir = snapshot_download(model_id, cache_dir=cache_dir)
            logger.info("魔搭下载完成: %s → %s", model_id, model_dir)
            return model_dir
        except Exception as exc:
            logger.warning("魔搭下载失败，回退到 HuggingFace: %s", exc)
            return None

    @classmethod
    def load_local_model(cls, model_name: str | None = None) -> None:
        """从本地缓存重新加载模型，不触发远程下载。

        按以下顺序查找：
          1. 上次下载/加载时保存的路径（_global_model_path）
          2. ModelScope 缓存目录
          3. HuggingFace 本地缓存（local_files_only=True）

        Raises:
            RuntimeError: 本地模型未找到时抛出
        """
        name = model_name or cls.MODEL_NAME
        cls._global_model = None
        cls._global_available = False

        candidates: list[str] = []

        # 1) 上次保存的路径
        if cls._global_model_path:
            candidates.append(cls._global_model_path)

        # 2) ModelScope 缓存
        try:
            from pathlib import Path

            from config.settings import settings

            ms_path = str(Path(settings.MODELSCOPE_CACHE) / "hub" / name)
            candidates.append(ms_path)
        except Exception:
            pass

        # 3) HuggingFace 本地缓存
        candidates.append(name)

        last_exc: Exception | None = None
        for path in candidates:
            try:
                from sentence_transformers import SentenceTransformer

                kwargs = {"trust_remote_code": True}
                if path == name:
                    kwargs["local_files_only"] = True
                model = SentenceTransformer(path, **kwargs)
                model.encode(["test"], show_progress_bar=False)
                cls._global_model = model
                cls._global_available = True
                cls._global_model._model_name = name
                cls._global_model_path = path
                logger.info("本地模型重新加载完成: %s ← %s", name, path)
                return
            except Exception as exc:
                last_exc = exc
                continue

        cls._global_available = False
        raise RuntimeError(f"本地模型未找到，请先下载: {last_exc}") from last_exc

    @classmethod
    def is_ready(cls) -> bool:
        """模型是否已加载就绪。"""
        return cls._global_available and cls._global_model is not None

    def _try_load(self) -> None:
        """在全局已就绪时加载本地引用。"""
        if self._global_available and self._global_model is not None:
            self._model = self._global_model
            self._available = True
        else:
            self._model = None
            self._available = False

    def __call__(self, input: Documents) -> Embeddings:
        if not self._available or self._model is None:
            self._try_load()
        if self._available and self._model is not None:
            return self._model.encode(input, show_progress_bar=False).tolist()
        raise RuntimeError(
            f"BGE embedding 模型未加载。请先在系统设置中下载模型："
            f"模型名称: {self._model_name}"
        )

    def name(self) -> str:
        return f"BGE({self._model_name})" if self._available else "BGE(unloaded)"
