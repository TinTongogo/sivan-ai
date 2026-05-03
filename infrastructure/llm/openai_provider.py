"""OpenAI SDK 封装 — 覆盖 OpenAI / DeepSeek / Ollama(OpenAI 兼容) / vLLM 等。"""

from __future__ import annotations

import logging
import re
from typing import Any

from openai import APIError as OpenAIAPIError
from openai import OpenAI

from infrastructure.llm.base import BaseLLMProvider, ChatResult, normalize_base_url

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL)


def _drain_think_tags(buffer: str, reasoning_callback=None) -> tuple[str, str]:
    """从 buffer 中提取完整 <thinking>...</thinking> 对，返回 (缓冲中剩余文本, 累计思考文本)。"""
    remaining = buffer
    visible_parts = []
    reasoning_parts = []
    while True:
        m = _THINK_RE.search(remaining)
        if not m:
            break
        visible_parts.append(remaining[: m.start()])
        think = m.group(1)
        if think:
            reasoning_parts.append(think)
            if reasoning_callback:
                reasoning_callback(think)
        remaining = remaining[m.end() :]
    # 可见文本 + 未闭合的剩余部分一起返回，由调用方决定如何处理
    result = "".join(visible_parts) + remaining
    return result, "".join(reasoning_parts)


class OpenAIProvider(BaseLLMProvider):
    """使用 openai SDK 调用 OpenAI 兼容 API。"""

    def _build_client(self) -> OpenAI:
        cfg = self._config
        api_key = cfg.get("api_key") or ""
        base_url = normalize_base_url(cfg.get("api_url", ""))
        timeout = int(cfg.get("timeout", 120))
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if timeout:
            kwargs["timeout"] = timeout
        return OpenAI(**kwargs)

    @staticmethod
    def _get_reasoning_content(delta: Any) -> str | None:
        """从 ChoiceDelta 获取 reasoning/thinking 文本，兼容不同 API/SDK。

        已知字段名差异：
          - reasoning         — Ollama（通常在 model_extra 中）
          - reasoning_content — OpenAI 标准 / vLLM
        """
        # 1. model_extra（Ollama 的 reasoning 字段在此）
        extra = getattr(delta, "model_extra", None)
        if extra and isinstance(extra, dict):
            val = extra.get("reasoning") or extra.get("reasoning_content")
            if val:
                return val
        # 2. 直接属性（reasoning_content 是 OpenAI SDK 原生字段）
        for field in ("reasoning_content", "reasoning"):
            val = getattr(delta, field, None)
            if val:
                return val
        return None

    def chat(self, messages: list[dict], stream_callback=None, reasoning_callback=None) -> ChatResult:
        client = self._build_client()
        cfg = self._config
        model = cfg.get("model") or "gpt-4o-mini"
        max_tokens = int(cfg.get("max_tokens", 0)) or 4096
        temperature = float(cfg.get("temperature", 0.7))

        kwargs: dict = dict(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        do_stream = stream_callback is not None
        if do_stream:
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}
            stream = client.chat.completions.create(**kwargs)
            full_text = ""
            reasoning_text = ""
            input_tokens = 0
            output_tokens = 0
            think_buf = ""  # 跨 chunk 的 think 标签缓冲
            for chunk in stream:
                if not chunk.choices:
                    if chunk.usage:
                        if chunk.usage.prompt_tokens:
                            input_tokens = chunk.usage.prompt_tokens
                        if chunk.usage.completion_tokens:
                            output_tokens = chunk.usage.completion_tokens
                    continue
                delta = chunk.choices[0].delta

                # 1. 原生 reasoning_content 字段（OpenAI SDK / vLLM / 部分 Ollama 版本）
                rc = self._get_reasoning_content(delta)
                if rc:
                    reasoning_text += rc
                    if reasoning_callback:
                        reasoning_callback(rc)

                # 2. content 中的 <thinking> 标签（Ollama 内联格式）
                if delta.content:
                    think_buf += delta.content
                    remaining, reasoning = _drain_think_tags(think_buf, reasoning_callback)
                    if reasoning:
                        reasoning_text += reasoning
                    if "<thinking>" not in remaining:
                        # 无未闭合标签 → 全部可输出
                        if remaining:
                            full_text += remaining
                            stream_callback(remaining)
                        think_buf = ""
                    else:
                        idx = remaining.index("<thinking>")
                        prefix = remaining[:idx]
                        if prefix:
                            full_text += prefix
                            stream_callback(prefix)
                        think_buf = remaining[idx:]

                # 3. 流式最后 chunk 携带 token 用量
                if chunk.usage:
                    if chunk.usage.prompt_tokens:
                        input_tokens = chunk.usage.prompt_tokens
                    if chunk.usage.completion_tokens:
                        output_tokens = chunk.usage.completion_tokens
            # 结束：think_buf 中剩余的未闭合 think 内容作为普通文本输出
            if think_buf:
                full_text += think_buf
                stream_callback(think_buf)
            return ChatResult(content=full_text, reasoning_content=reasoning_text,
                              input_tokens=input_tokens, output_tokens=output_tokens)
        else:
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            reasoning = getattr(resp.choices[0].message, "reasoning_content", None) or ""
            input_tokens = resp.usage.prompt_tokens if resp.usage else 0
            output_tokens = resp.usage.completion_tokens if resp.usage else 0
            return ChatResult(content=content, reasoning_content=reasoning,
                              input_tokens=input_tokens, output_tokens=output_tokens)

    def test_connection(self) -> dict[str, Any]:
        cfg = self._config
        name = cfg.get("name", "?")
        model = cfg.get("model") or "gpt-4o-mini"
        try:
            client = self._build_client()
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello, respond with exactly: OK"}],
                max_tokens=50,
                temperature=0,
            )
            content = resp.choices[0].message.content or ""
            return {"success": True, "provider": name, "model": model, "response": content[:200]}
        except OpenAIAPIError as e:
            return {"success": False, "error": f"OpenAI API Error: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_models(self) -> list[str]:
        try:
            client = self._build_client()
            models = client.models.list()
            return sorted(m.id for m in models)
        except OpenAIAPIError as e:
            logger.warning("OpenAI 获取模型列表失败: %s", e)
            return []
        except Exception as e:
            logger.warning("获取模型列表失败: %s", e)
            return []
