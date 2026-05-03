"""数据访问服务层 — 按领域拆分为独立模块。

所有函数为无状态顶层函数，以 db_path 为首参数，
供 routes/ 下各模块调用。

使用方式保持不变:
  from interfaces.api.services import get_system_stats, get_agents_list
"""

from interfaces.api.services.agents import (
    create_agent,
    delete_agent,
    get_agent_detail,
    get_agents_count,
    get_agents_list,
    update_agent,
)
from interfaces.api.services.base import _connect, _get_cursor
from interfaces.api.services.contracts import (
    delete_contract,
    delete_contracts_batch,
    get_contract_detail,
    get_contract_graph,
    get_contracts_count,
    get_contracts_list,
)
from interfaces.api.services.memory import (
    memory_archive,
    memory_batch,
    memory_delete,
    memory_find_by_scope,
    memory_get,
    memory_list,
    memory_retention,
    memory_retention_status,
    memory_search,
    memory_stats,
    memory_store,
    memory_toggle_important,
    memory_unarchive,
    memory_update,
)
from interfaces.api.services.reports import (
    check_and_generate_weekly_report,
    collect_system_stats_for_report,
    delete_weekly_report,
    download_weekly_report_html,
    generate_weekly_report,
    get_active_subscriptions,
    get_subscriptions,
    get_weekly_report_detail,
    get_weekly_reports,
    publish_weekly_report,
    subscribe_report,
    unsubscribe_report,
)
from interfaces.api.services.routing import (
    batch_delete_routing_decisions,
    delete_routing_decision,
    get_recent_decisions,
    get_routing_filter_options,
    get_routing_stats,
    get_routing_stats_summary,
    get_routing_strategy_trend,
    get_routing_trend,
    submit_routing_feedback,
)
from interfaces.api.services.settings import (
    delete_setting,
    get_all_settings,
    get_llm_settings,
    get_setting,
    get_settings_by_category,
    init_default_settings,
    set_setting,
    test_llm_connection,
)
from interfaces.api.services.skills import (
    check_skill_archiving,
    delete_skill,
    get_agent_skill_usage,
    get_skill_detail,
    get_skill_usage_trend,
    get_skills_count,
    get_skills_list,
    get_skills_stats,
    update_skill,
)
from interfaces.api.services.squads import (
    _resolve_agent_repo,
    advance_squad_execution,
    call_agent_for_squad,
    create_squad,
    delete_squad,
    delete_squads_batch,
    execute_dynamic_squad,
    execute_squad_hitl,
    execute_squad_impl,
    get_orchestration_pattern,
    get_orchestration_patterns,
    get_squad_detail,
    get_squad_execution_detail,
    get_squad_executions,
    get_squads_list,
    get_squads_stats,
    update_squad,
)
from interfaces.api.services.instinct_patterns import (
    instinct_delete,
    instinct_get,
    instinct_list,
    instinct_stats,
    instinct_toggle_active,
)
from interfaces.api.services.topology_feedback import (
    topology_feedback_list,
    topology_feedback_record,
    topology_feedback_stats,
)
from interfaces.api.services.system import get_system_stats
from interfaces.api.services.tokens import (
    check_budget_alerts,
    delete_token_usage,
    get_token_daily_trend,
    get_token_stats,
    get_token_stats_summary,
    update_token_budget,
)

__all__ = [
    "_connect", "_get_cursor",
    "get_all_settings", "get_setting", "set_setting", "delete_setting",
    "get_settings_by_category", "get_llm_settings", "test_llm_connection", "init_default_settings",
    "get_system_stats",
    "get_agents_count", "get_agents_list", "create_agent", "get_agent_detail", "update_agent", "delete_agent",
    "get_contracts_count", "get_contracts_list", "get_contract_detail", "get_contract_graph",
    "delete_contract", "delete_contracts_batch",
    "get_token_stats_summary", "get_token_stats", "get_token_daily_trend", "delete_token_usage", "update_token_budget", "check_budget_alerts",
    "get_routing_stats_summary", "get_routing_stats", "get_routing_trend", "get_routing_strategy_trend",
    "get_recent_decisions", "get_routing_filter_options", "submit_routing_feedback",
    "get_skills_count", "get_skills_list", "get_skill_detail", "get_skills_stats", "get_skill_usage_trend",
    "get_agent_skill_usage", "update_skill", "delete_skill", "check_skill_archiving",
    "get_squads_list", "get_squad_detail", "get_squads_stats", "create_squad", "update_squad", "delete_squad",
    "delete_squads_batch",
    "get_squad_executions", "get_squad_execution_detail", "get_orchestration_patterns", "get_orchestration_pattern",
    "_resolve_agent_repo", "call_agent_for_squad", "execute_dynamic_squad", "execute_squad_impl", "execute_squad_hitl", "advance_squad_execution",
    "get_weekly_reports", "get_weekly_report_detail", "generate_weekly_report", "collect_system_stats_for_report",
    "publish_weekly_report", "delete_weekly_report", "download_weekly_report_html",
    "subscribe_report", "unsubscribe_report", "get_subscriptions", "get_active_subscriptions",
    "check_and_generate_weekly_report",
    "publish_weekly_report", "delete_weekly_report", "download_weekly_report_html",
    "subscribe_report", "unsubscribe_report", "get_subscriptions", "get_active_subscriptions",
    "memory_stats", "memory_list", "memory_store", "memory_get", "memory_update", "memory_delete",
    "memory_search", "memory_find_by_scope", "memory_retention", "memory_retention_status",
    "memory_archive", "memory_unarchive", "memory_batch", "memory_toggle_important",
    "instinct_list", "instinct_get", "instinct_stats", "instinct_toggle_active", "instinct_delete",
    "topology_feedback_stats", "topology_feedback_list", "topology_feedback_record",
]
