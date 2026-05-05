"""路由应用服务。

组合路由领域服务与仓储，提供路由决策用例。
装配 5 种路由策略（semantic、ml、context_aware、adaptive 及集成路由器）。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from domain.routing.entity import RoutingDecision, RoutingStrategy
from domain.routing.service import RoutingService as DomainRoutingService
from domain.routing.strategy import (
    AdaptiveRouter,
    ContextAwareRouter,
    MLRouter,
    SemanticRouter,
)
from infrastructure.ml.classifier import SklearnMLClassifier
from infrastructure.persistence.routing_repo import RoutingRepository

logger = logging.getLogger("sivan.routing")


class RoutingService:
    """路由应用服务。

    装配所有路由策略，提供统一的路由决策入口：
    - semantic: 中文分词 + 同义词扩展（语义匹配）
    - ml: 基于 scikit-learn 的文本分类
    - context_aware: 8 维度上下文感知
    - adaptive: 动态权重自适应（默认）
    -- 集成路由器由 domain.routing.service.RoutingService 承担
    """

    STRATEGY_SEMANTIC = "semantic"
    STRATEGY_ML = "ml"
    STRATEGY_CONTEXT = "context_aware"
    STRATEGY_ADAPTIVE = "adaptive"

    def __init__(
        self,
        domain_service: DomainRoutingService,
        routing_repo: RoutingRepository,
        model_dir: str | None = None,
    ) -> None:
        self._domain = domain_service
        self._repo = routing_repo
        self._adaptive_router: AdaptiveRouter | None = None
        self._init_strategies(model_dir)

    def _init_strategies(self, model_dir: str | None = None) -> None:
        """创建并注册所有路由策略。"""

        # 1. SemanticRouter
        semantic = SemanticRouter()
        self._load_semantic_features(semantic)

        # 2. MLRouter
        ml_router = MLRouter()
        if model_dir:
            classifier = SklearnMLClassifier(model_dir)
            if classifier.load():
                ml_router.classifier = classifier
                logger.info("ML 分类器已加载")
            else:
                logger.info("ML 分类器未找到已训练模型，尝试从历史数据训练...")
                self._try_train_ml(classifier, ml_router)

        # 3. ContextAwareRouter
        context = ContextAwareRouter()

        # 注册到 domain service
        self._domain.register_strategy(self.STRATEGY_SEMANTIC, semantic)
        self._domain.register_strategy(self.STRATEGY_ML, ml_router)
        self._domain.register_strategy(self.STRATEGY_CONTEXT, context)

        # 4. AdaptiveRouter 包装所有子策略
        adaptive = AdaptiveRouter(strategies={
            self.STRATEGY_SEMANTIC: semantic,
            self.STRATEGY_ML: ml_router,
            self.STRATEGY_CONTEXT: context,
        })
        self._domain.register_strategy(self.STRATEGY_ADAPTIVE, adaptive)
        self._adaptive_router = adaptive

        # 默认使用自适应路由器
        self._domain.switch_strategy(self.STRATEGY_ADAPTIVE)

    def _load_semantic_features(self, semantic: SemanticRouter) -> None:
        """从 DB 加载关键词特征到语义路由器。"""
        try:
            features = self._repo.get_keyword_features()
            if features:
                weights: dict[str, dict[str, float]] = {}
                for f in features:
                    kw = f["keyword"]
                    agent = f["agent_name"]
                    rate = f.get("success_rate") or 0.5
                    weights.setdefault(kw, {})[agent] = rate
                semantic.set_feature_weights(weights)
                logger.info("语义路由器加载了 %d 个关键词特征", len(features))
        except Exception as exc:
            logger.warning("加载关键词特征失败: %s", exc)

    def _try_train_ml(self, classifier: SklearnMLClassifier, ml_router: MLRouter) -> None:
        """尝试从历史路由决策数据训练 ML 模型。"""
        try:
            texts, labels = self._repo.get_ml_training_data(limit=2000)
            if len(texts) >= 10 and len(set(labels)) >= 2:
                classifier.train(texts, labels)
                ml_router.classifier = classifier
                logger.info("ML 模型从 %d 条历史数据训练完成", len(texts))
            else:
                logger.info("ML 训练数据不足（%d 条，%d 个类别），跳过训练", len(texts), len(set(labels)))
        except Exception as exc:
            logger.warning("ML 模型训练失败: %s", exc)

    def route(self, task_description: str, context: dict[str, Any]) -> str | None:
        """路由任务到最合适的智能体（使用当前策略）。"""
        from infrastructure.logging.db_logger import get_db_logger

        start_time = time.time()
        db_log = get_db_logger()

        existing_trace_id = (context or {}).pop("trace_id", None) or ""
        trace_id, _ = db_log.trace("routing", "route", task_description[:200],
                                   {"task_len": len(task_description)},
                                   trace_id=existing_trace_id)

        agent = self._domain.route(task_description, context)
        elapsed_ms = int((time.time() - start_time) * 1000)

        decision = RoutingDecision(
            task_description=task_description,
            selected_agent=agent,
            decision_id=trace_id,
            routing_strategy=RoutingStrategy(self._domain.current_strategy),
            context_json=json.dumps(context, ensure_ascii=False) if context else None,
            execution_time_ms=elapsed_ms,
        )
        decision_id = self._repo.record_decision(decision)

        db_log.log("INFO", "routing", "route_result", agent or "none",
                   trace_id=trace_id, duration_ms=elapsed_ms,
                   metadata={"task": task_description[:100], "agent": agent,
                             "strategy": self._domain.current_strategy})

        return agent

    def route_with_all_strategies(self, task_description: str, context: dict[str, Any]) -> dict[str, Any]:
        """用所有策略分别路由，返回各策略结果和自适应结果。"""
        start_time = time.time()
        results: dict[str, Any] = {}

        for name in self._domain.list_strategies():
            s_time = time.time()
            agent = self._domain.route_with_strategy(task_description, context, name)
            elapsed = int((time.time() - s_time) * 1000)
            results[name] = {"selected_agent": agent, "execution_time_ms": elapsed}

        adaptive_agent = results.get(self.STRATEGY_ADAPTIVE, {}).get("selected_agent")
        adaptive_time = results.get(self.STRATEGY_ADAPTIVE, {}).get("execution_time_ms", 0)

        choices: dict[str, list[str]] = {}
        for name, data in results.items():
            agent = data["selected_agent"]
            if agent:
                choices.setdefault(agent, []).append(name)

        consensus_agent = max(choices.items(), key=lambda x: len(x[1]))[0] if choices else None

        total_elapsed = int((time.time() - start_time) * 1000)

        return {
            "strategies": results,
            "adaptive": adaptive_agent,
            "adaptive_time_ms": adaptive_time,
            "consensus": consensus_agent,
            "total_time_ms": total_elapsed,
        }

    def record_feedback(
        self,
        decision_id: int,
        success: bool,
        strategy_name: str | None = None,
    ) -> bool:
        """记录路由反馈，更新策略性能和关键词特征。

        Args:
            decision_id: 路由决策 ID。
            success: 是否成功。
            strategy_name: 可选，策略名称（用于更新自适应权重）。
        """
        from domain.routing.entity import UserFeedback

        feedback = UserFeedback(
            decision_id=decision_id,
            feedback_type="success" if success else "failure",
            corrected_agent="",
            feedback_text="",
            rating=1.0 if success else 0.0,
        )
        ok = self._repo.record_feedback(decision_id, feedback)
        if not ok:
            return False

        if strategy_name:
            self._repo.update_strategy_performance(strategy_name, success)
        if self._adaptive_router and strategy_name:
            self._adaptive_router.record_feedback(strategy_name, success)

        return True

    def get_analytics(self) -> dict[str, Any]:
        analytics = self._repo.get_analytics()
        analytics["routers"] = {}

        features = self._repo.get_keyword_features()
        analytics["routers"]["semantic"] = {"total_semantic_features": len(features)}

        ml_router = self._domain.get_strategy(self.STRATEGY_ML)
        if ml_router and isinstance(ml_router, MLRouter) and ml_router.classifier:
            analytics["routers"]["ml"] = {"is_trained": ml_router.classifier.is_trained}
        else:
            analytics["routers"]["ml"] = {"is_trained": False}

        if self._adaptive_router:
            analytics["routers"]["adaptive"] = {
                "weights": self._adaptive_router.weights,
                "strategy_names": self._adaptive_router.strategy_names,
            }

        strategy_perf = self._repo.get_strategy_performance()
        analytics["strategy_performance"] = strategy_perf

        return analytics

    def get_recent_decisions(self, limit: int = 10) -> list[dict[str, Any]]:
        decisions = self._repo.find_decisions(limit=limit)
        return [d.to_dict() for d in decisions]

    def get_agent_performance(self, agent_name: str) -> dict[str, Any]:
        return self._repo.get_agent_performance(agent_name)

    def switch_strategy(self, strategy_name: str) -> None:
        self._domain.switch_strategy(strategy_name)

    def add_agent(self, agent_name: str, capabilities: list[str]) -> None:
        self._domain.add_agent(agent_name, capabilities)

    def provide_feedback(self, decision_id: int, success: bool) -> bool:
        """简化版反馈接口，委托给 record_feedback。"""
        return self.record_feedback(decision_id, success)
