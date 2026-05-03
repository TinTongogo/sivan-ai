"""路由领域服务。

聚合所有路由策略，提供统一的路由决策入口。
"""

from __future__ import annotations

from typing import Any

from domain.routing.strategy import IRoutingStrategy


class RoutingService:
    """路由领域服务。

    聚合多策略路由决策：
    - 委托具体策略执行路由
    - 跨策略分析 (analyze_task)
    - 反馈学习
    - 动态策略切换
    """

    def __init__(
        self,
        strategies: dict[str, IRoutingStrategy] | None = None,
        default_strategy: str = "",
    ) -> None:
        self._strategies: dict[str, IRoutingStrategy] = strategies or {}
        self._current = default_strategy
        self._agents: dict[str, list[str]] = {}

    @property
    def current_strategy(self) -> str:
        return self._current

    def register_strategy(self, name: str, strategy: IRoutingStrategy) -> None:
        """注册路由策略。"""
        self._strategies[name] = strategy

    def add_agent(self, agent_name: str, capabilities: list[str]) -> None:
        """添加智能体到所有策略。"""
        self._agents[agent_name] = capabilities
        for strategy in self._strategies.values():
            strategy.add_agent(agent_name, capabilities)

    def remove_agent(self, agent_name: str) -> None:
        """从所有策略移除智能体。"""
        self._agents.pop(agent_name, None)
        for strategy in self._strategies.values():
            strategy.remove_agent(agent_name)

    def route(self, task_description: str, context: dict[str, Any]) -> str | None:
        """使用当前策略路由任务。"""
        strategy = self._strategies.get(self._current)
        if not strategy:
            raise ValueError(f"未知的路由策略: {self._current}")
        return strategy.route(task_description, context)

    def route_with_strategy(
        self, task_description: str, context: dict[str, Any], strategy_name: str
    ) -> str | None:
        """使用指定策略路由。"""
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            raise ValueError(f"未知的路由策略: {strategy_name}")
        return strategy.route(task_description, context)

    def switch_strategy(self, strategy_name: str) -> None:
        """切换当前策略。"""
        if strategy_name not in self._strategies:
            raise ValueError(f"未知的路由策略: {strategy_name}")
        self._current = strategy_name

    def analyze_task(
        self, task_description: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """分析任务，获取所有策略的结果和共识。"""
        results: dict[str, Any] = {}

        for name, strategy in self._strategies.items():
            agent = strategy.route(task_description, context)
            results[name] = {"selected_agent": agent}

        # 共识分析
        choices: dict[str, list[str]] = {}
        for name, data in results.items():
            agent = data["selected_agent"]
            if agent:
                choices.setdefault(agent, []).append(name)

        consensus_agent = None
        if choices:
            consensus_agent = max(choices.items(), key=lambda x: len(x[1]))[0]

        results["consensus"] = {
            "agent": consensus_agent,
            "strategy_support": choices.get(consensus_agent, []),
            "agreement": (
                len(choices.get(consensus_agent, [])) / len(self._strategies)
                if consensus_agent and self._strategies
                else 0.0
            ),
        }

        return results

    def list_strategies(self) -> list[str]:
        """列出所有已注册的策略名称。"""
        return list(self._strategies.keys())

    def get_strategy(self, name: str) -> IRoutingStrategy | None:
        """获取指定名称的策略实例。"""
        return self._strategies.get(name)

    def list_agents(self) -> dict[str, list[str]]:
        return dict(self._agents)
