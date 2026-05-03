"""通用智能体 — 配置驱动，适用于所有智能体。"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from infrastructure.agents.base import BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """智能体配置。"""
    agent_id: str
    display_name: str
    description: str
    system_prompt: str
    craft_declaration: str = ""
    tools: list[str] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)


class GenericAgent(BaseAgent):
    """通用智能体，适用于所有智能体。"""

    def __init__(self, config: AgentConfig, db_conn, skill_loader=None, kb_service=None) -> None:
        core_config = {
            "type": "generic",
            "skills": config.skill_ids,
            "tool_permissions": config.tools,
            "description": config.description,
        }
        super().__init__(name=config.agent_id, config=core_config)
        self.agent_config = config
        self.db = db_conn
        self.skill_loader = skill_loader
        self.kb_service = kb_service
        self._skills_content: dict[str, str] = {}
        # 技能延迟加载 — 在 _select_relevant_skills 中按需触发

    def _load_skills_content(self) -> None:
        if self._skills_content:
            return  # 已加载，跳过
        for skill_id in self.agent_config.skill_ids:
            if self.skill_loader:
                skill = self.skill_loader.get(skill_id)
                if skill:
                    self._skills_content[skill_id] = skill.content
            else:
                skill = self._load_skill_from_db(skill_id)
                if skill:
                    self._skills_content[skill_id] = skill

    def _select_relevant_skills(self, task_description: str) -> dict[str, str]:
        """根据任务描述关键词筛选相关技能，无匹配时回退到全部技能。"""
        if not self.agent_config.skill_ids:
            return {}
        # 按需懒加载
        if not self._skills_content:
            self._load_skills_content()
        if not self._skills_content:
            return {}

        task_lower = task_description.lower()
        task_words = set(re.findall(r'[a-z0-9一-鿿]+', task_lower))
        if not task_words:
            return dict(self._skills_content)  # 空任务：返回全部

        def _score(skill_id: str) -> int:
            score = 0
            # 技能 ID 匹配（权重高）
            sid_tokens = set(re.findall(r'[a-z0-9]+', skill_id.lower()))
            score += len(sid_tokens & task_words) * 4
            # 从数据库查元数据
            try:
                cursor = self.db.cursor()
                cursor.execute(
                    "SELECT name, description, category FROM skills WHERE skill_id = ?",
                    (skill_id,),
                )
                row = cursor.fetchone()
                if row:
                    for field in ("name", "description", "category"):
                        text = (row[field] or "").lower()
                        tokens = set(re.findall(r'[a-z0-9一-鿿]+', text))
                        weight = {"name": 5, "description": 3, "category": 2}.get(field, 1)
                        score += len(tokens & task_words) * weight
            except Exception:
                pass
            return score

        scored = [(sid, _score(sid)) for sid in self._skills_content]
        scored.sort(key=lambda x: (-x[1], x[0]))
        relevant = {sid: self._skills_content[sid] for sid, s in scored if s >= 1}
        return relevant if relevant else dict(self._skills_content)

    def _load_skill_from_db(self, skill_id: str) -> str | None:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT content FROM skills WHERE skill_id = ? AND status = 'active'",
            (skill_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def _execute_core(self, task_description: str, context: dict[str, Any]) -> Any:
        # 按任务筛选相关技能
        self._selected_skills = self._select_relevant_skills(task_description)

        full_prompt = self._build_full_prompt(context)
        messages = [{"role": "system", "content": full_prompt}]

        # 注入多轮对话历史（按 token 预算截取）
        history = context.pop("_history", []) if isinstance(context, dict) else []
        if history:
            MAX_HISTORY_TOKENS = 60000
            recent = []
            total = 0
            for entry in reversed(history):
                tokens = self._estimate_tokens(entry["content"])
                if total + tokens > MAX_HISTORY_TOKENS:
                    break
                recent.append(entry)
                total += tokens
            recent.reverse()
            messages.extend(recent)

        messages.append({"role": "user", "content": task_description})
        existing_trace_id = context.pop("trace_id", None) if isinstance(context, dict) else None
        stream_callback = context.pop("_stream_callback", None) if isinstance(context, dict) else None
        reasoning_callback = context.pop("_reasoning_callback", None) if isinstance(context, dict) else None
        response = self._call_llm(messages, stream_callback=stream_callback,
                                  reasoning_callback=reasoning_callback, existing_trace_id=existing_trace_id)
        if isinstance(context, dict):
            context["_token_used"] = getattr(self, "_last_token_used", 0)
            context["_token_input"] = getattr(self, "_last_input_tokens", 0)
            context["_token_output"] = getattr(self, "_last_output_tokens", 0)
            context["_token_model"] = getattr(self, "_last_model", "")
            context["_reasoning_content"] = getattr(self, "_last_reasoning_content", "")
        output = self._parse_response(response)
        self._update_usage_stats()
        return output

    def _preprocess_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """预处理上下文：根据 project_id 检索对应知识库，注入 RAG 上下文。"""
        context = super()._preprocess_context(context)
        task_desc = context.get("task_description", "") or ""
        if self.kb_service and task_desc:
            try:
                project_id = context.get("project_id", "")
                if project_id:
                    from config.settings import settings as _settings
                    from infrastructure.persistence.connection import SQLiteConnectionManager
                    from infrastructure.persistence.project_repo import ProjectRepository
                    from application.services.project_service import ProjectService
                    mgr = SQLiteConnectionManager.get_instance(_settings.DB_PATH)
                    repo = ProjectRepository(mgr)
                    svc = ProjectService(repo)
                    kb_names = svc.get_kb_names_for_project(self.kb_service, project_id)
                    results = self.kb_service.search_by_kb_names(kb_names, task_desc, top_k=3)
                else:
                    results = self.kb_service.search_all(task_desc, top_k=3)
                if results:
                    context["_rag_context"] = self._format_rag_results(results)
            except Exception:
                pass
        return context

    def _build_full_prompt(self, context: dict[str, Any]) -> str:
        parts = [self.agent_config.system_prompt]
        # 行为约束：抑制内心独白，角色融入行为而非口号
        parts.append("\n\n【行为规则】直接回答任务，不要角色自述，不要复述身份，不要逐条检查职责清单。用行动体现专业，而不是用语言宣告身份。")
        # RAG 上下文注入
        if isinstance(context, dict):
            rag = context.pop("_rag_context", None)
            if rag:
                parts.append(rag)
        selected = getattr(self, "_selected_skills", self._skills_content)
        if selected:
            parts.append(f"\n## 加载的技能（{len(selected)}/{len(self.agent_config.skill_ids)}）\n")
            for skill_id, content in selected.items():
                parts.append(f"### {skill_id}\n{content}\n")
        return "\n".join(parts)

    @staticmethod
    def _format_rag_results(results: list[dict]) -> str:
        lines = ["\n[知识库参考信息（回答问题时可参考以下内容）]"]
        for r in results:
            meta = r.get("metadata", {})
            source = meta.get("source", "未知")
            heading = meta.get("heading", "")
            tag = f" > {heading}" if heading else ""
            lines.append(f"[{r['kb_name']}{tag}] {r['text'][:300]}")
        return "\n".join(lines)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算 token 数（~4 字符/token，适用中英混合）。"""
        return len(text) // 4 + 1

    def _get_active_provider_from_db(self) -> dict | None:
        """从 llm_providers 表读取当前激活的提供商，无表或无记录时返回 None。"""
        try:
            cursor = self.db.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='llm_providers'")
            if not cursor.fetchone():
                return None
            cursor.execute("SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)
        except Exception:
            return None

    def _call_llm(self, messages: list[dict], stream_callback=None,
                  reasoning_callback=None, existing_trace_id: str | None = None) -> str:
        from infrastructure.logging.db_logger import get_db_logger
        db_log = get_db_logger()

        self._last_token_used = 0
        self._last_input_tokens = 0
        self._last_output_tokens = 0
        self._last_reasoning_content = ""
        start = time.time()
        trace_id, _ = db_log.trace(
            "generic_agent", "llm_call_start",
            f"Agent={self.agent_config.agent_id}, messages={len(messages)}",
            {"agent": self.agent_config.agent_id, "message_count": len(messages)},
            trace_id=existing_trace_id or "",
        )

        # 从激活的提供商读取配置
        active_provider = self._get_active_provider_from_db()
        if not active_provider:
            active_provider = {
                "auth_type": "OpenAI",
                "api_key": "",
                "api_url": "",
                "model": "claude-sonnet-4-20250514",
                "max_tokens": "4096",
                "temperature": "0.7",
                "timeout": "120",
                "api_version": "",
                "name": "",
            }

        provider_name = active_provider.get("name", "?")
        model = active_provider.get("model", "claude-sonnet-4-20250514")
        self._last_model = model

        if not active_provider.get("api_url"):
            logger.info("[模拟] 激活的提供商 '%s' 配置不完整（缺 URL），返回模拟结果", provider_name)
            if stream_callback:
                stream_callback(f"[{self.agent_config.agent_id}] 已处理任务: {messages[-1]['content'][:50]}...")
            elapsed = int((time.time() - start) * 1000)
            db_log.log("WARNING", "generic_agent", "llm_call_simulated", "LLM提供者配置不完整",
                       trace_id=trace_id, duration_ms=elapsed,
                       metadata={"agent": self.agent_config.agent_id, "provider": provider_name})
            return f"[{self.agent_config.agent_id}] 已处理任务: {messages[-1]['content'][:50]}..."

        if not active_provider.get("model"):
            logger.warning("激活的提供商 '%s' 未配置模型，使用默认: %s", provider_name, model)
            db_log.log("WARNING", "generic_agent", "model_not_configured",
                       f"provider={provider_name}, fallback_model={model}",
                       trace_id=trace_id,
                       metadata={"agent": self.agent_config.agent_id, "provider": provider_name, "fallback_model": model})

        try:
            from infrastructure.llm.factory import create_llm_provider

            provider = create_llm_provider(active_provider)
            result = provider.chat(messages, stream_callback=stream_callback,
                                   reasoning_callback=reasoning_callback)

            elapsed = int((time.time() - start) * 1000)
            self._last_token_used = result.total_tokens
            self._last_input_tokens = result.input_tokens
            self._last_output_tokens = result.output_tokens
            self._last_reasoning_content = result.reasoning_content
            db_log.log("INFO", "generic_agent", "llm_call_success", f"model={model}",
                       trace_id=trace_id, duration_ms=elapsed,
                       metadata={
                           "agent": self.agent_config.agent_id,
                           "model": model,
                           "input_tokens": result.input_tokens,
                           "output_tokens": result.output_tokens,
                       })
            return result.content

        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            db_log.log("ERROR", "generic_agent", "llm_call_failed", str(e),
                       trace_id=trace_id, duration_ms=elapsed,
                       metadata={"agent": self.agent_config.agent_id, "error": str(e)[:200]})
            logger.error("LLM API 调用失败: %s", e)
            raise

    def _parse_response(self, response: str) -> Any:
        return response

    def _auto_refine(self, task: str, output: Any, history: list) -> Any:
        return output

    def _update_usage_stats(self) -> None:
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE agents SET last_used_at = CURRENT_TIMESTAMP, "
            "usage_count = COALESCE(usage_count, 0) + 1 "
            "WHERE agent_id = ?",
            (self.agent_config.agent_id,),
        )
        self.db.commit()

    def get_capabilities(self) -> list[str]:
        return self.agent_config.skill_ids
