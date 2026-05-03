"""LLM 提供商量体工厂 — 根据配置返回对应的 provider 实例。"""

from __future__ import annotations

from typing import Any

from infrastructure.llm.anthropic_provider import AnthropicProvider
from infrastructure.llm.base import BaseLLMProvider
from infrastructure.llm.openai_provider import OpenAIProvider


def create_llm_provider(config: dict[str, Any]) -> BaseLLMProvider:
    """根据配置字典创建对应的 LLM 提供商量体。

    配置字典应包含以下键（与 llm_providers 表列对齐）：
        auth_type : str  — "Anthropic" 或 "OpenAI"（默认）
        api_key   : str
        api_url   : str
        model     : str
        max_tokens: int/str
        temperature: float/str
        timeout   : int/str
        api_version: str
    """
    auth_type = config.get("auth_type", "OpenAI")
    if auth_type == "Anthropic":
        return AnthropicProvider(config)
    return OpenAIProvider(config)
