"""Anthropic SDK 封装 — 覆盖 Claude 全系列模型。"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic
from anthropic import APIError as AnthropicAPIError

from infrastructure.llm.base import BaseLLMProvider, ChatResult, normalize_base_url

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """使用 anthropic SDK 调用 Anthropic API。"""

    def _build_client(self) -> Anthropic:
        cfg = self._config
        api_key = cfg.get("api_key") or ""
        base_url = normalize_base_url(cfg.get("api_url", ""))
        api_version = cfg.get("api_version") or ""
        timeout = int(cfg.get("timeout", 120))
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if api_version:
            kwargs["auth_headers"] = {"anthropic-version": api_version}
        if timeout:
            kwargs["timeout"] = timeout
        return Anthropic(**kwargs)

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """提取 system 消息为顶层字段，Anthropic SDK 不支持 messages 中 role=system。"""
        if messages and messages[0].get("role") == "system":
            return messages[0]["content"], messages[1:]
        return None, messages

    def chat(self, messages: list[dict], stream_callback=None, reasoning_callback=None) -> ChatResult:
        client = self._build_client()
        cfg = self._config
        model = cfg.get("model") or "claude-sonnet-4-20250514"
        max_tokens = int(cfg.get("max_tokens", 0)) or 4096
        temperature = float(cfg.get("temperature", 0.7))

        system, chat_messages = self._split_system(messages)

        kwargs: dict = dict(
            model=model,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if system:
            kwargs["system"] = system

        do_stream = stream_callback is not None
        if do_stream:
            with client.messages.stream(**kwargs) as stream:
                full_text = ""
                reasoning_text = ""
                input_tokens = 0
                output_tokens = 0
                # 迭代 parsed 事件流，比 _raw_stream 更易用
                for event in stream:
                    # thinking 块启动（含 signature + 首次 thinking）
                    if event.type == "content_block_start":
                        cb = getattr(event, "content_block", None)
                        if cb and getattr(cb, "type", None) == "thinking":
                            rt = getattr(cb, "thinking", None) or ""
                            if rt:
                                reasoning_text += rt
                                if reasoning_callback:
                                    reasoning_callback(rt)
                    # 流式 thinking delta
                    elif event.type == "thinking":
                        rt = getattr(event, "thinking", None) or ""
                        if rt:
                            reasoning_text += rt
                            if reasoning_callback:
                                reasoning_callback(rt)
                    # 流式 text delta
                    elif event.type == "text":
                        t = getattr(event, "text", None) or ""
                        full_text += t
                        stream_callback(t)
                    # token 用量
                    elif event.type == "message_start":
                        msg = getattr(event, "message", None)
                        if msg:
                            usage = getattr(msg, "usage", None)
                            if usage:
                                input_tokens = getattr(usage, "input_tokens", 0)
                    elif event.type == "message_delta":
                        usage = getattr(event, "usage", None)
                        if usage:
                            output_tokens = getattr(usage, "output_tokens", 0)
            return ChatResult(content=full_text, reasoning_content=reasoning_text,
                              input_tokens=input_tokens, output_tokens=output_tokens)
        else:
            resp = client.messages.create(**kwargs)
            content = resp.content[0].text if resp.content else ""
            input_tokens = resp.usage.input_tokens if resp.usage else 0
            output_tokens = resp.usage.output_tokens if resp.usage else 0
            return ChatResult(content=content, input_tokens=input_tokens, output_tokens=output_tokens)

    def test_connection(self) -> dict[str, Any]:
        cfg = self._config
        name = cfg.get("name", "?")
        model = cfg.get("model") or "claude-sonnet-4-20250514"
        try:
            client = self._build_client()
            resp = client.messages.create(
                model=model,
                max_tokens=50,
                temperature=0,
                messages=[{"role": "user", "content": "Hello, respond with exactly: OK"}],
            )
            content = resp.content[0].text if resp.content else ""
            return {"success": True, "provider": name, "model": model, "response": content[:200]}
        except AnthropicAPIError as e:
            return {"success": False, "error": f"Anthropic API Error: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_models(self) -> list[str]:
        return []
