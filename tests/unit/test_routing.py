"""路由策略单元测试。"""

from __future__ import annotations

from typing import Any

import pytest

from domain.routing.strategy import (
    AdaptiveRouter,
    ContextAwareRouter,
    SemanticRouter,
)


# ================================================================
# SemanticRouter 测试
# ================================================================


class TestSemanticRouter:
    def test_route_backend_task(self, sample_agents: dict[str, list[str]]) -> None:
        router = SemanticRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        result = router.route("设计用户登录API，包括数据库表结构", {})
        assert result == "be-dev"

    def test_route_frontend_task(self, sample_agents: dict[str, list[str]]) -> None:
        router = SemanticRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        result = router.route("实现一个响应式导航栏组件", {})
        assert result == "fe-dev"

    def test_route_security_task(self, sample_agents: dict[str, list[str]]) -> None:
        router = SemanticRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        result = router.route("对系统进行安全渗透测试", {})
        assert result == "security-auditor"

    def test_empty_agents_returns_none(self) -> None:
        router = SemanticRouter()
        result = router.route("任何任务", {})
        assert result is None

    def test_remove_agent(self, sample_agents: dict[str, list[str]]) -> None:
        router = SemanticRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)
        router.remove_agent("be-dev")

        result = router.route("设计API接口", {})
        # 可能会路由到其他智能体，但不会是 be-dev
        assert result != "be-dev"

    def test_synonym_expansion(self, sample_agents: dict[str, list[str]]) -> None:
        router = SemanticRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        # "发布" 是 devops 领域关键词，应路由到 devops
        result = router.route("发布应用到Kubernetes集群", {})
        assert result == "devops"

    def test_synonym_expansion_expands_terms(self) -> None:
        """验证同义词扩展能找到反向映射（deploy → 部署 → devops 领域）。"""
        router = SemanticRouter()
        router.add_agent("devops", ["CI/CD"])
        # deploy 是 "部署" 的同义词，扩展后 devops 领域匹配
        expanded = router._expand_synonyms(["deploy"])
        assert "部署" in expanded

    def test_feature_weights(self, sample_agents: dict[str, list[str]]) -> None:
        router = SemanticRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        router.set_feature_weights({"API": {"be-dev": 0.9}})
        result = router.route("API设计", {})
        assert result == "be-dev"


# ================================================================
# ContextAwareRouter 测试
# ================================================================


class TestContextAwareRouter:
    def test_route_with_domain(self, sample_agents: dict[str, list[str]]) -> None:
        router = ContextAwareRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        result = router.route("实现用户登录", {"domain": "frontend"})
        assert result == "fe-dev"

    def test_route_with_complexity(self, sample_agents: dict[str, list[str]]) -> None:
        router = ContextAwareRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        result = router.route("架构设计评审", {"domain": "architecture", "complexity": 5})
        assert result == "architect"

    def test_route_with_security_context(self, sample_agents: dict[str, list[str]]) -> None:
        router = ContextAwareRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        result = router.route("代码安全审查", {"domain": "security", "security": "high"})
        assert result == "security-auditor"

    def test_parse_context_defaults(self) -> None:
        """验证 _parse_context 对缺失字段使用安全默认值（P0 回归测试）。"""
        router = ContextAwareRouter()
        ctx = router._parse_context({})
        assert ctx["complexity"] == 3
        assert ctx["domain"] == ""
        assert ctx["collaboration"] is False
        assert ctx["security"] == "medium"

    def test_empty_agents_returns_none(self) -> None:
        router = ContextAwareRouter()
        result = router.route("任何任务", {"domain": "backend"})
        assert result is None

    def test_record_outcome_updates_profile(self, sample_agents: dict[str, list[str]]) -> None:
        router = ContextAwareRouter()
        for name, caps in sample_agents.items():
            router.add_agent(name, caps)

        router.record_outcome("be-dev", success=True)
        profile = router.get_profile("be-dev")
        assert profile is not None
        assert profile.success_count == 1
        assert profile.total_count == 1

    def test_get_profile_nonexistent(self) -> None:
        router = ContextAwareRouter()
        assert router.get_profile("ghost") is None


# ================================================================
# AdaptiveRouter 测试
# ================================================================


class TestAdaptiveRouter:
    def test_route_delegates_to_best_strategy(self, routing_service: Any) -> None:
        result = routing_service.route("设计用户登录API", {"domain": "backend"})
        assert result is not None

    def test_fallback_when_no_agents(self) -> None:
        router = AdaptiveRouter()
        result = router.route("任务", {})
        assert result is None  # 没有后备智能体

    def test_strategy_weights_initialized(self) -> None:
        from domain.routing.strategy import SemanticRouter, ContextAwareRouter

        sr = SemanticRouter()
        cr = ContextAwareRouter()
        router = AdaptiveRouter(strategies={"semantic": sr, "context": cr})
        assert "semantic" in router.weights
        assert "context" in router.weights

    def test_record_feedback_updates_metrics(self) -> None:
        from domain.routing.strategy import SemanticRouter

        sr = SemanticRouter()
        router = AdaptiveRouter(strategies={"semantic": sr})
        router.record_feedback("semantic", success=True, confidence=0.9, execution_time_ms=100)
        metrics = router._metrics["semantic"]
        assert metrics.total == 1
        assert metrics.success == 1
        assert metrics.confidence_sum == 0.9


# ================================================================
# 集成路由 (DomainRoutingService) 测试
# ================================================================


class TestDomainRoutingService:
    def test_route_with_strategy(self, routing_service: Any) -> None:
        result = routing_service.route_with_strategy(
            "设计用户登录API", {"domain": "backend"}, "context_aware",
        )
        assert result is not None

    def test_switch_strategy(self, routing_service: Any) -> None:
        routing_service.switch_strategy("semantic")
        assert routing_service.current_strategy == "semantic"
        result = routing_service.route("测试", {})
        assert result is not None

    def test_switch_to_unknown_strategy(self, routing_service: Any) -> None:
        with pytest.raises(ValueError, match="未知的路由策略"):
            routing_service.switch_strategy("nonexistent")

    def test_analyze_task_returns_all_strategies(self, routing_service: Any) -> None:
        analysis = routing_service.analyze_task("部署应用到Kubernetes", {"domain": "devops"})
        assert "consensus" in analysis
        assert analysis["consensus"]["agent"] is not None
        assert analysis["consensus"]["agreement"] > 0

    def test_list_strategies(self, routing_service: Any) -> None:
        strategies = routing_service.list_strategies()
        assert "semantic" in strategies
        assert "context_aware" in strategies
        assert "adaptive" in strategies
        assert "ml" in strategies

    def test_list_agents(self, routing_service: Any, sample_agents: dict[str, list[str]]) -> None:
        agents = routing_service.list_agents()
        assert len(agents) == len(sample_agents)
        for name in sample_agents:
            assert name in agents
