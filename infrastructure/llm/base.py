"""LLM 提供商量体抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChatResult:
    """一次 LLM chat 调用的结果。"""
    content: str
    reasoning_content: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BaseLLMProvider(ABC):
    """LLM 提供商量体基类。所有提供商量体实现此接口。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config

    @abstractmethod
    def chat(self, messages: list[dict], stream_callback=None, reasoning_callback=None) -> ChatResult:
        """发送消息列表，返回 ChatResult。"""
        ...

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        """测试连接，返回 UI 层需要的 dict。"""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """获取可用模型列表。"""
        ...


def normalize_base_url(url: str) -> str:
    """从用户配置的完整 api_url 中提取 SDK 所需的 base URL。

    用户可能在 api_url 中填入完整的 chat/completions 路径，
    SDK 需要的是不带 /chat/completions 的 base URL。
    """
    url = url.rstrip("/")
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")]
    return url
