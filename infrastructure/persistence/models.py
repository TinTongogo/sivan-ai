"""集中式数据库表定义（SQLAlchemy Core Metadata）。

所有表的 schema 以此处为准。FTS5 虚拟表（kb_documents_fts）除外，
因其在 kb_repo.py 中手动管理。
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sa_text

metadata = MetaData()

# ── 智能体 ────────────────────────────────────────────────────

agents = Table(
    "agents", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("agent_id", Text, unique=True, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("description", Text),
    Column("category", Text, server_default=""),
    Column("system_prompt", Text, nullable=False, server_default=""),
    Column("craft_declaration", Text),
    Column("tools", Text, server_default="[]"),
    Column("skill_ids", Text, server_default="[]"),
    Column("status", Text, server_default="active"),
    Column("version", Text, server_default="1.0.0"),
    Column("created_by", Text, server_default=""),
    Column("usage_count", Integer, server_default="0"),
    Column("last_used_at", Text),  # TIMESTAMP
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

# ── 技能 ──────────────────────────────────────────────────────

skills = Table(
    "skills", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("skill_id", Text, unique=True, nullable=False),
    Column("name", Text, nullable=False),
    Column("display_name", Text),
    Column("description", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("argument_hint", Text),
    Column("allowed_tools", Text),
    Column("category", Text, nullable=False),
    Column("maintainer_agent", Text),
    Column("tags", Text),
    Column("usage_count", Integer, server_default="0"),
    Column("last_used_at", Text),
    Column("status", Text, server_default="active"),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

skill_tags = Table(
    "skill_tags", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("skill_id", Text, nullable=False),
    Column("tag", Text, nullable=False),
    UniqueConstraint("skill_id", "tag"),
)

skill_usage = Table(
    "skill_usage", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("skill_id", Text, nullable=False),
    Column("agent_name", Text),
    Column("timestamp", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("context_json", Text),
)

# ── 知识库 ────────────────────────────────────────────────────

knowledge_bases = Table(
    "knowledge_bases", metadata,
    Column("kb_name", Text, primary_key=True),
    Column("description", Text, server_default=""),
    Column("document_count", Integer, server_default="0"),
    Column("chunk_count", Integer, server_default="0"),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

kb_documents = Table(
    "kb_documents", metadata,
    Column("doc_id", Text, primary_key=True),
    Column("kb_name", Text, ForeignKey("knowledge_bases.kb_name"), nullable=False),
    Column("filename", Text, nullable=False),
    Column("source_path", Text, nullable=False),
    Column("file_type", Text, nullable=False),
    Column("chunk_count", Integer, server_default="0"),
    Column("char_count", Integer, server_default="0"),
    Column("text_content", Text, server_default=""),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

# kb_documents_fts — FTS5 虚拟表，在 kb_repo.py 中手动创建，不在此处定义

# ── 记忆 ──────────────────────────────────────────────────────

memory_entries = Table(
    "memory_entries", metadata,
    Column("memory_id", Text, primary_key=True),
    Column("level", Text, nullable=False),
    Column("scope_id", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("metadata_json", Text, server_default="{}"),
    Column("created_at", Text, nullable=False),
    Column("last_accessed_at", Text, nullable=False),
    Column("access_count", Integer, server_default="0"),
    Column("retention", Float, server_default="1.0"),
    Column("is_archived", Integer, server_default="0"),
    Column("is_important", Integer, server_default="0"),
    Column("summary", Text),
)

# ── Token 用量 ────────────────────────────────────────────────

token_usage = Table(
    "token_usage", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("agent_name", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("input_tokens", Integer, server_default="0"),
    Column("output_tokens", Integer, server_default="0"),
    Column("total_tokens", Integer, server_default="0"),
    Column("cost_usd", Float, server_default="0.0"),
    Column("task_description", Text),
    Column("timestamp", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("metadata_json", Text),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

daily_budgets = Table(
    "daily_budgets", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", Text, unique=True, nullable=False),
    Column("budget_usd", Float, server_default="0.0"),
    Column("spent_usd", Float, server_default="0.0"),
    Column("alert_sent", Boolean, server_default=sa_text("FALSE")),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

token_budget = Table(
    "token_budget", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("daily_budget", Float, server_default="10.0"),
    Column("daily_budget_usd", Float, server_default="0.0"),
    Column("monthly_budget", Float, server_default="300.0"),
    Column("monthly_budget_usd", Float, server_default="0.0"),
    Column("alert_threshold", Float, server_default="0.8"),
    Column("alert_email", Text),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

# ── 路由决策 ──────────────────────────────────────────────────

routing_decisions = Table(
    "routing_decisions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("decision_id", Text),
    Column("task_description", Text, nullable=False),
    Column("task_hash", Text),
    Column("selected_agent", Text),
    Column("routing_strategy", Text, server_default="keyword"),
    Column("status", Text, server_default="success"),
    Column("confidence_score", Float),
    Column("execution_time_ms", Float),
    Column("context_json", Text),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("user_id", Text),
    Column("session_id", Text),
)

candidate_scores = Table(
    "candidate_scores", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("decision_id", Integer, ForeignKey("routing_decisions.id")),
    Column("agent_name", Text, nullable=False),
    Column("score", Float, server_default="0.0"),
    Column("rank", Integer, server_default="0"),
    Column("features_json", Text),
)

user_feedback = Table(
    "user_feedback", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("decision_id", Integer, ForeignKey("routing_decisions.id")),
    Column("feedback_type", Text, server_default="correct"),
    Column("corrected_agent", Text),
    Column("feedback_text", Text),
    Column("rating", Integer),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

agent_performance = Table(
    "agent_performance", metadata,
    Column("agent_name", Text, primary_key=True),
    Column("total_tasks", Integer, server_default="0"),
    Column("success_count", Integer, server_default="0"),
    Column("avg_confidence", Float),
    Column("avg_execution_time_ms", Float),
    Column("last_updated", Text),
)

strategy_performance = Table(
    "strategy_performance", metadata,
    Column("strategy_name", Text, primary_key=True),
    Column("total_decisions", Integer, server_default="0"),
    Column("success_rate", Float),
    Column("avg_confidence", Float),
    Column("avg_execution_time_ms", Float),
    Column("feedback_correct_rate", Float),
    Column("weight", Float, server_default="1.0"),
)

keyword_features = Table(
    "keyword_features", metadata,
    Column("keyword", Text, nullable=False),
    Column("agent_name", Text, nullable=False),
    Column("occurrence_count", Integer, server_default="0"),
    Column("success_rate", Float),
    Column("last_used", Text),
    PrimaryKeyConstraint("keyword", "agent_name"),
)

# ── 契约 ──────────────────────────────────────────────────────

contracts = Table(
    "contracts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("contract_id", Text, unique=True, nullable=False),
    Column("contract_type", Text, nullable=False),
    Column("content_json", Text, nullable=False),
    Column("created_by", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("version", Text, server_default="1.0.0"),
    Column("status", Text, server_default="draft"),
    Column("metadata_json", Text),
)

contract_tags = Table(
    "contract_tags", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("contract_id", Text, ForeignKey("contracts.contract_id", ondelete="CASCADE"), nullable=False),
    Column("tag", Text, nullable=False),
    UniqueConstraint("contract_id", "tag"),
)

contract_dependencies = Table(
    "contract_dependencies", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("contract_id", Text, ForeignKey("contracts.contract_id", ondelete="CASCADE"), nullable=False),
    Column("depends_on_contract_id", Text, nullable=False),
    UniqueConstraint("contract_id", "depends_on_contract_id"),
)

contract_versions = Table(
    "contract_versions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("contract_id", Text, ForeignKey("contracts.contract_id", ondelete="CASCADE"), nullable=False),
    Column("version", Text, nullable=False),
    Column("content_json", Text, nullable=False),
    Column("created_by", Text, nullable=False, server_default=""),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("change_description", Text),
)

# ── Squad ─────────────────────────────────────────────────────

squads = Table(
    "squads", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("squad_id", Text, unique=True, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text),
    Column("version", Text, server_default="1.0.0"),
    Column("status", Text, server_default="active"),
    Column("category", Text),
    Column("workflow_type", Text, server_default="sequential"),
    Column("max_parallel_agents", Integer, server_default="1"),
    Column("estimated_duration_days", Integer, server_default="7"),
    Column("quality_gates_json", Text),
    Column("success_metrics_json", Text),
    Column("created_by", Text),
    Column("parent_squad_id", Text),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("last_executed_at", Text),
    Column("execution_count", Integer, server_default="0"),
    Column("success_count", Integer, server_default="0"),
)

squad_workflows = Table(
    "squad_workflows", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("squad_id", Text, nullable=False),
    Column("phase", Integer, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text),
    Column("mode", Text, server_default="sequential"),
    Column("parent_phase", Integer),
    Column("conditions_json", Text),
    Column("consensus_threshold", Float, server_default="0.5"),
    Column("estimated_duration_hours", Integer, server_default="24"),
    Column("max_duration_hours", Integer, server_default="48"),
    Column("sort_order", Integer, server_default="0"),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    UniqueConstraint("squad_id", "phase"),
)

squad_agents = Table(
    "squad_agents", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("squad_id", Text, nullable=False),
    Column("phase", Integer, nullable=False),
    Column("agent_name", Text, nullable=False),
    Column("role", Text),
    Column("sort_order", Integer, server_default="0"),
    Column("is_lead", Boolean, server_default=sa_text("FALSE")),
    Column("weight", Float, server_default="1.0"),
    Column("conditions_json", Text),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    UniqueConstraint("squad_id", "phase", "agent_name"),
)

squad_executions = Table(
    "squad_executions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("execution_id", Text, unique=True, nullable=False),
    Column("squad_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text),
    Column("status", Text, server_default="pending"),
    Column("current_phase", Integer, server_default="1"),
    Column("progress_percent", Float, server_default="0"),
    Column("started_at", Text),
    Column("completed_at", Text),
    Column("estimated_completion_at", Text),
    Column("actual_duration_hours", Float),
    Column("result_json", Text),
    Column("outputs_json", Text),
    Column("metrics_json", Text),
    Column("error_message", Text),
    Column("error_details_json", Text),
    Column("retry_count", Integer, server_default="0"),
    Column("created_by", Text),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

squad_phase_executions = Table(
    "squad_phase_executions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("execution_id", Text, nullable=False),
    Column("phase", Integer, nullable=False),
    Column("phase_name", Text, nullable=False),
    Column("status", Text, server_default="pending"),
    Column("primary_agent", Text, nullable=False),
    Column("supporting_agents_json", Text),
    Column("started_at", Text),
    Column("completed_at", Text),
    Column("duration_minutes", Float),
    Column("outputs_json", Text),
    Column("success_criteria_met_json", Text),
    Column("metrics_json", Text),
    Column("error_message", Text),
    Column("error_details_json", Text),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    UniqueConstraint("execution_id", "phase"),
)

# ── 周报 ──────────────────────────────────────────────────────

weekly_reports = Table(
    "weekly_reports", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("report_id", Text, unique=True, nullable=False),
    Column("report_type", Text, server_default="weekly"),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("generated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("total_executions", Integer, server_default="0"),
    Column("successful_executions", Integer, server_default="0"),
    Column("failed_executions", Integer, server_default="0"),
    Column("avg_duration_hours", Float, server_default="0"),
    Column("active_squads", Integer, server_default="0"),
    Column("most_used_squad", Text),
    Column("most_successful_squad", Text),
    Column("top_performing_agents_json", Text),
    Column("most_used_agents_json", Text),
    Column("routing_decisions_total", Integer, server_default="0"),
    Column("routing_success_rate", Float, server_default="0"),
    Column("top_routing_strategies_json", Text),
    Column("total_tokens_used", Integer, server_default="0"),
    Column("total_cost_usd", Float, server_default="0"),
    Column("cost_by_agent_json", Text),
    Column("cost_by_model_json", Text),
    Column("total_skills_used", Integer, server_default="0"),
    Column("most_used_skills_json", Text),
    Column("skill_usage_trend_json", Text),
    Column("contracts_created", Integer, server_default="0"),
    Column("contracts_approved", Integer, server_default="0"),
    Column("contract_types_distribution_json", Text),
    Column("performance_trend_json", Text),
    Column("improvement_areas_json", Text),
    Column("recommendations_json", Text),
    Column("summary_markdown", Text),
    Column("detailed_analysis_json", Text),
    Column("charts_config_json", Text),
    Column("generated_by", Text, server_default="system"),
    Column("is_published", Boolean, server_default=sa_text("FALSE")),
    Column("published_at", Text),
)

report_subscriptions = Table(
    "report_subscriptions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", Text, nullable=False),
    Column("report_type", Text, nullable=False),
    Column("delivery_method", Text, server_default="email"),
    Column("delivery_config_json", Text),
    Column("is_active", Boolean, server_default=sa_text("TRUE")),
    Column("subscribed_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("unsubscribed_at", Text),
    UniqueConstraint("email", "report_type"),
)

# ── 编排模式 ──────────────────────────────────────────────────

orchestration_patterns = Table(
    "orchestration_patterns", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("pattern_id", Text, unique=True, nullable=False),
    Column("name", Text, nullable=False),
    Column("display_name", Text),
    Column("description", Text),
    Column("long_description", Text),
    Column("icon", Text, server_default="bi-diagram-3"),
    Column("color", Text, server_default="#4361ee"),
    Column("workflow_type", Text, nullable=False),
    Column("default_phases_json", Text),
    Column("flow_rules_json", Text),
    Column("suitable_for_json", Text),
    Column("sort_order", Integer, server_default="0"),
    Column("is_active", Boolean, server_default=sa_text("TRUE")),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

# ── 系统设置 ──────────────────────────────────────────────────

settings_t = Table(
    "settings", metadata,
    Column("key", Text, primary_key=True, nullable=False),
    Column("value", Text, nullable=False, server_default=""),
    Column("value_type", Text, nullable=False, server_default="str"),
    Column("description", Text, server_default=""),
    Column("category", Text, nullable=False, server_default="general"),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

llm_providers = Table(
    "llm_providers", metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("auth_type", Text, nullable=False, server_default="OpenAI"),
    Column("api_url", Text, nullable=False, server_default=""),
    Column("api_key", Text, nullable=False, server_default=""),
    Column("model", Text, nullable=False, server_default=""),
    Column("api_version", Text, nullable=False, server_default=""),
    Column("max_tokens", Integer, nullable=False, server_default="4096"),
    Column("temperature", Float, nullable=False, server_default="0.7"),
    Column("timeout", Integer, nullable=False, server_default="120"),
    Column("is_active", Integer, nullable=False, server_default="0"),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

# ── 执行日志 ──────────────────────────────────────────────────

execution_logs = Table(
    "execution_logs", metadata,
    Column("log_id", Integer, primary_key=True, autoincrement=True),
    Column("trace_id", Text, nullable=False),
    Column("parent_log_id", Integer, ForeignKey("execution_logs.log_id")),
    Column("timestamp", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("level", Text, nullable=False, server_default="INFO"),
    Column("source", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("message", Text, nullable=False),
    Column("metadata", Text, server_default="{}"),
    Column("project_id", Text, server_default=""),
    Column("duration_ms", Integer, server_default="0"),
)

# ── 对话 ──────────────────────────────────────────────────────

conversations = Table(
    "conversations", metadata,
    Column("conversation_id", Text, primary_key=True),
    Column("project_id", Text, nullable=False, server_default="default"),
    Column("title", Text, nullable=False, server_default="新对话"),
    Column("status", Text, nullable=False, server_default="active"),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

messages = Table(
    "messages", metadata,
    Column("message_id", Text, primary_key=True),
    Column("conversation_id", Text, ForeignKey("conversations.conversation_id"), nullable=False),
    Column("parent_id", Text, ForeignKey("messages.message_id")),
    Column("role", Text, nullable=False),
    Column("agent_name", Text),
    Column("content", Text, nullable=False),
    Column("metadata", Text, server_default="{}"),
    Column("status", Text, nullable=False, server_default="completed"),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("trace_id", Text, server_default=""),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

conversation_agents = Table(
    "conversation_agents", metadata,
    Column("conversation_id", Text, ForeignKey("conversations.conversation_id"), nullable=False),
    Column("agent_name", Text, nullable=False),
    Column("task_count", Integer, nullable=False, server_default="0"),
    PrimaryKeyConstraint("conversation_id", "agent_name"),
)

# ── 项目隔离 ──

projects = Table(
    "projects", metadata,
    Column("project_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("description", Text, server_default=""),
    Column("status", Text, nullable=False, server_default="active"),
    Column("created_by", Text, server_default=""),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

kb_project_assignments = Table(
    "kb_project_assignments", metadata,
    Column("kb_name", Text, nullable=False),
    Column("project_id", Text, nullable=False),
    PrimaryKeyConstraint("kb_name", "project_id"),
)

# ── 本能模板 ──

instinct_patterns = Table(
    "instinct_patterns", metadata,
    Column("pattern_id", Text, primary_key=True),
    Column("task_type", Text, nullable=False),
    Column("task_signature", Text, nullable=False),
    Column("topology_json", Text, nullable=False),
    Column("success_count", Integer, server_default="0"),
    Column("total_count", Integer, server_default="0"),
    Column("confidence", Float, server_default="0.0"),
    Column("is_active", Integer, server_default="0"),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
    Column("updated_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

# ── 拓扑反馈 ──

topology_feedback = Table(
    "topology_feedback", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_signature", Text, nullable=False),
    Column("topology", Text, nullable=False),
    Column("satisfaction", Float, nullable=False),
    Column("execution_id", Text, server_default=""),
    Column("created_at", Text, server_default=sa_text("CURRENT_TIMESTAMP")),
)

