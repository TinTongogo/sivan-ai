"""路由策略接口与内置策略实现。

定义 IRoutingStrategy 接口及 4 种策略：
- SemanticRouter：中文分词 + 同义词扩展 + 特征权重
- MLRouter：基于 scikit-learn 的文本分类
- ContextAwareRouter：8 维度上下文感知
- AdaptiveRouter：动态权重自适应
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class IRoutingStrategy(ABC):
    """路由策略接口 (Strategy 模式)。

    所有具体策略（语义 / ML / 上下文感知 / 自适应）均实现此接口。
    """

    @abstractmethod
    def route(self, task_description: str, context: dict[str, Any]) -> str | None:
        """路由任务到最合适的智能体。

        Args:
            task_description: 自然语言任务描述。
            context: 上下文维度字典（策略按需取用，如 domain、security 等）。

        Returns:
            智能体名称，None 表示无匹配。
        """
        ...

    @abstractmethod
    def add_agent(self, agent_name: str, capabilities: list[str]) -> None:
        """添加智能体到路由表。"""
        ...

    @abstractmethod
    def remove_agent(self, agent_name: str) -> None:
        """从路由表移除智能体。"""
        ...


# ================================================================
# 1. SemanticRouter —— 语义路由器
# ================================================================


class SemanticRouter(IRoutingStrategy):
    """语义路由器：中文分词 + 同义词扩展 + 意图分析 + 特征权重。

    领域服务，依赖 jieba（轻量库）进行中文分词。
    """

    # 领域 → 中文关键词映射（辅助意图分类）
    DOMAIN_KEYWORDS: dict[str, set[str]] = {
        "frontend": {"前端", "页面", "界面", "组件", "UI", "CSS", "HTML", "交互", "动效"},
        "backend": {"后端", "API", "接口", "数据库", "认证", "微服务", "缓存", "消息"},
        "devops": {"部署", "CI/CD", "Docker", "Kubernetes", "监控", "运维", "发布", "流水线"},
        "testing": {"测试", "QA", "质量", "自动化", "性能测试", "回归", "覆盖率"},
        "architecture": {"架构", "技术选型", "系统设计", "ADR", "高可用", "扩展性"},
        "product": {"需求", "用户故事", "产品", "优先级", "功能", "验收", "PRD"},
        "design": {"设计", "视觉", "用户体验", "色彩", "图标", "原型", "Figma"},
        "security": {"安全", "漏洞", "渗透", "威胁", "加密", "认证", "OAuth"},
        "data": {"数据", "ETL", "管道", "数据仓库", "分析", "BI", "报表"},
        "ml": {"模型", "训练", "推理", "ML", "LLM", "RAG", "检索", "NLP", "视觉", "语音"},
    }

    # 同义词库
    SYNONYMS: dict[str, list[str]] = {
        "前端": ["前端开发", "前端工程", "web前端", "前端页面"],
        "后端": ["后端开发", "后端工程", "服务端", "服务器端"],
        "API": ["接口", "REST接口", "API接口", "端点", "endpoint"],
        "数据库": ["DB", "数据存储", "持久化", "数据层"],
        "部署": ["发布", "上线", "更新", "deploy", "发布上线"],
        "测试": ["测试用例", "单元测试", "集成测试", "自动化测试", "UT"],
        "安全": ["安全性", "security", "防护", "加固"],
        "监控": ["监控告警", "可观测性", "observability", "metrics", "链路追踪"],
        "缓存": ["cache", "redis缓存", "高速缓存"],
        "性能": ["性能优化", "性能调优", "高并发", "响应时间"],
    }

    # 意图权重：每类意图对智能体的影响
    INTENT_AGENT_WEIGHTS: dict[str, dict[str, float]] = {
        "frontend": {"fe-dev": 1.0, "mobile-dev": 0.6},
        "backend": {"be-dev": 1.0, "architect": 0.3},
        "devops": {"devops": 1.0},
        "testing": {"qa": 1.0, "be-dev": 0.2},
        "architecture": {"architect": 1.0, "be-dev": 0.3},
        "product": {"po": 1.0},
        "design": {"ui-ux": 1.0, "fe-dev": 0.3},
        "security": {"security-auditor": 1.0, "be-dev": 0.3},
        "data": {"data-engineer": 1.0},
        "ml": {"mlops": 0.8, "inference-engineer": 0.8, "rag-engineer": 0.8, "vision-engineer": 0.6, "speech-engineer": 0.5},
    }

    def __init__(self, feature_weights: dict[str, dict[str, float]] | None = None) -> None:
        self._agents: dict[str, list[str]] = {}
        # keyword → agent → weight（从 keyword_features 表加载）
        self._feature_weights: dict[str, dict[str, float]] = feature_weights or {}

    def add_agent(self, agent_name: str, capabilities: list[str]) -> None:
        self._agents[agent_name] = [c.lower() for c in capabilities]

    def remove_agent(self, agent_name: str) -> None:
        self._agents.pop(agent_name, None)
        for kw in self._feature_weights:
            self._feature_weights[kw].pop(agent_name, None)

    def set_feature_weights(self, weights: dict[str, dict[str, float]]) -> None:
        self._feature_weights = weights

    # ---- 分词 ----

    def _segment(self, text: str) -> list[str]:
        """jieba 中文分词 + 英文 token 提取。"""
        import jieba
        words = list(jieba.cut(text, cut_all=False))
        eng_tokens = re.findall(r"[a-z][a-z0-9\-_]*", text.lower())
        result = [w.strip() for w in words if len(w.strip()) > 0]
        result.extend(eng_tokens)
        return result

    # ---- 同义词扩展 ----

    def _expand_synonyms(self, tokens: list[str]) -> set[str]:
        """对分词结果做同义词扩展。"""
        expanded = set(tokens)
        for token in tokens:
            if token in self.SYNONYMS:
                expanded.update(self.SYNONYMS[token])
            # 反向查找：token 是否作为某词的同义词
            for word, syns in self.SYNONYMS.items():
                if token in syns:
                    expanded.add(word)
        return expanded

    # ---- 意图分析 ----

    def _detect_intents(self, tokens: list[str]) -> dict[str, float]:
        """检测任务所属领域意图，返回 领域 → 置信度。"""
        text = "".join(tokens)
        scores: dict[str, float] = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text)
            if matches > 0:
                scores[domain] = matches / len(keywords)
        # 归一化
        if scores:
            total = sum(scores.values())
            scores = {k: v / total for k, v in scores.items()}
        return scores

    # ---- 评分 ----

    def _score(self, agent_name: str, capabilities: list[str],
               tokens: list[str], expanded: set[str],
               intents: dict[str, float]) -> float:
        """计算智能体对任务的匹配得分（浮点数，支持精细排序）。"""
        score = 0.0
        token_set = set(tokens)
        text = " ".join(tokens)

        # 1. 能力匹配（0-5 分）
        cap_lower = [c.lower() for c in capabilities]
        for cap in cap_lower:
            if cap in text:
                score += 3.0
            elif any(t in cap for t in token_set if len(t) > 2):
                score += 1.0

        # 2. 同义词扩展匹配（0-2 分）
        for term in expanded:
            for cap in cap_lower:
                if term.lower() in cap or cap in term.lower():
                    score += 0.5
                    break

        # 3. 特征权重（0-3 分）
        for kw, agent_weights in self._feature_weights.items():
            if kw in token_set and agent_name in agent_weights:
                score += agent_weights[agent_name] * 2.0

        # 4. 意图加成（0-2 分）
        for domain, confidence in intents.items():
            agent_weight = self.INTENT_AGENT_WEIGHTS.get(domain, {}).get(agent_name, 0)
            score += confidence * agent_weight * 2.0

        return score

    def route(self, task_description: str, context: dict[str, Any]) -> str | None:
        if not self._agents:
            return None

        tokens = self._segment(task_description)
        expanded = self._expand_synonyms(tokens)
        intents = self._detect_intents(tokens)

        best_agent: str | None = None
        best_score = -1.0

        for agent_name, capabilities in self._agents.items():
            s = self._score(agent_name, capabilities, tokens, expanded, intents)
            if s > best_score:
                best_score = s
                best_agent = agent_name

        return best_agent


# ================================================================
# 2. MLRouter —— 机器学习路由器
# ================================================================


class MLRouter(IRoutingStrategy):
    """ML 路由器：基于 scikit-learn 的文本分类。

    领域层仅定义编排逻辑，ML 训练/推理委托给 MLClassifierPort。
    """

    def __init__(self, classifier: Any = None) -> None:  # MLClassifierPort | None
        self._agents: dict[str, list[str]] = {}
        self._classifier: Any = classifier  # MLClassifierPort

    # ---- 分类器注入（基础设施层通过此处注入 sklearn 实现） ----

    @property
    def classifier(self) -> Any:
        return self._classifier

    @classifier.setter
    def classifier(self, clf: Any) -> None:
        self._classifier = clf

    def add_agent(self, agent_name: str, capabilities: list[str]) -> None:
        self._agents[agent_name] = [c.lower() for c in capabilities]

    def remove_agent(self, agent_name: str) -> None:
        self._agents.pop(agent_name, None)

    def route(self, task_description: str, context: dict[str, Any]) -> str | None:
        """委托 ML 分类器预测，返回概率最高的智能体。

        未训练或无分类器时返回 None，调用方（AdaptiveRouter）会回退到其他策略。
        """
        if not self._agents or self._classifier is None:
            return None

        try:
            agent_names = list(self._agents.keys())
            if not self._classifier.is_trained:
                return None
            scores = self._classifier.predict(task_description, agent_names)
            if not scores:
                return None
            return max(scores, key=scores.get)
        except Exception:
            return None


# ================================================================
# 3. ContextAwareRouter —— 上下文感知路由器
# ================================================================


@dataclass
class ContextProfile:
    """智能体上下文偏好画像。"""
    agent_name: str
    # 各维度偏好向量 (0.0 ~ 1.0 表示该智能体擅长处理此维度的程度)
    complexity_prefs: list[float] = None  # 简单 → 复杂
    domain_affinities: dict[str, float] = None  # 领域 → 亲和度
    collaboration_pref: float = 0.5  # 协作需求
    quality_pref: float = 0.5  # 质量要求
    security_pref: float = 0.5  # 安全要求
    success_count: int = 0
    total_count: int = 0

    def __post_init__(self):
        if self.complexity_prefs is None:
            self.complexity_prefs = [0.5, 0.5, 0.5]
        if self.domain_affinities is None:
            self.domain_affinities = {}

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.total_count, 1)


class ContextAwareRouter(IRoutingStrategy):
    """上下文感知路由器：8 维度上下文分析 + 智能体画像 + 实时学习。

    上下文 dict 支持以下键：
    - complexity: int 1-5（任务复杂度）
    - domain: str（领域标签）
    - user_expertise: str beginner|intermediate|expert
    - time_constraint: str low|medium|high
    - collaboration: bool 是否需要多智能体协作
    - quality: str low|medium|high（质量要求）
    - security: str low|medium|high（安全要求）
    - session_context: str（对话上下文提示）
    """

    # 领域标签 → 智能体初始亲和度
    DOMAIN_AFFINITY: dict[str, dict[str, float]] = {
        "frontend": {"fe-dev": 1.0, "mobile-dev": 0.8, "ui-ux": 0.7},
        "backend": {"be-dev": 1.0, "architect": 0.5, "data-engineer": 0.3},
        "devops": {"devops": 1.0, "security-auditor": 0.3},
        "testing": {"qa": 1.0, "be-dev": 0.2},
        "architecture": {"architect": 1.0, "po": 0.3},
        "product": {"po": 1.0, "ui-ux": 0.3, "architect": 0.3},
        "design": {"ui-ux": 1.0, "fe-dev": 0.4},
        "security": {"security-auditor": 1.0, "be-dev": 0.3, "devops": 0.3},
        "data": {"data-engineer": 1.0, "be-dev": 0.3},
        "ml": {"mlops": 0.8, "inference-engineer": 0.8, "rag-engineer": 0.8,
               "vision-engineer": 0.6, "speech-engineer": 0.6, "data-engineer": 0.3},
    }

    # 复杂度映射：complexity int → 画像索引
    COMPLEXITY_LEVELS = {1: 0, 2: 0, 3: 1, 4: 2, 5: 2}

    def __init__(self) -> None:
        self._agents: dict[str, list[str]] = {}
        self._profiles: dict[str, ContextProfile] = {}

    def add_agent(self, agent_name: str, capabilities: list[str]) -> None:
        self._agents[agent_name] = [c.lower() for c in capabilities]
        if agent_name not in self._profiles:
            self._profiles[agent_name] = ContextProfile(agent_name=agent_name)

    def remove_agent(self, agent_name: str) -> None:
        self._agents.pop(agent_name, None)
        self._profiles.pop(agent_name, None)

    # ---- 画像查询与反馈学习 ----

    def get_profile(self, agent_name: str) -> ContextProfile | None:
        return self._profiles.get(agent_name)

    def record_outcome(self, agent_name: str, success: bool) -> None:
        """反馈学习：记录路由结果更新画像。"""
        profile = self._profiles.get(agent_name)
        if profile is None:
            return
        profile.total_count += 1
        if success:
            profile.success_count += 1

    def _parse_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """提取并规范化上下文维度。

        未提供的维度使用中性默认值：
        - complexity 默认 3（中等），domain 默认空（不限制）
        - user_expertise / time_constraint 默认 medium
        - quality / security 默认 medium
        - collaboration 默认 False
        """
        domain = context.get("domain", "") if isinstance(context.get("domain"), str) else ""
        user_expertise = context.get("user_expertise", "intermediate")
        time_constraint = context.get("time_constraint", "medium")
        collaboration = bool(context.get("collaboration", False))
        quality = context.get("quality", "medium")
        security = context.get("security", "medium")
        return {
            "complexity": complexity,
            "domain": domain,
            "user_expertise": user_expertise,
            "time_constraint": time_constraint,
            "collaboration": collaboration,
            "quality": quality,
            "security": security,
        }

    def _score_agent(self, agent_name: str, ctx: dict[str, Any]) -> float:
        """计算智能体与上下文匹配度。"""
        profile = self._profiles.get(agent_name)
        capabilities = self._agents.get(agent_name, [])
        score = 0.0

        # 1. 领域匹配 (0-3 分)
        domain = ctx["domain"]
        if domain:
            affinities = self.DOMAIN_AFFINITY.get(domain, {})
            score += affinities.get(agent_name, 0) * 3.0

        # 2. 复杂度匹配 (0-2 分)
        if profile:
            ci = self.COMPLEXITY_LEVELS.get(ctx["complexity"], 1)
            pref = profile.complexity_prefs[ci]
            score += pref * 2.0

        # 3. 能力基线 (0-2 分)
        if capabilities:
            score += 1.0  # 有能力的智能体基础分

        # 4. 协作需求 (0-1 分)
        if ctx["collaboration"]:
            collab_agents = {"orchestrator", "po", "architect"}
            if agent_name in collab_agents:
                score += 1.0

        # 5. 安全要求 (0-1 分)
        if ctx["security"] in ("high",):
            if agent_name == "security-auditor":
                score += 1.0

        # 6. 历史成功率加成 (0-1 分)
        if profile and profile.total_count > 0:
            score += profile.success_rate * 1.0

        return score

    def route(self, task_description: str, context: dict[str, Any]) -> str | None:
        if not self._agents:
            return None

        ctx = self._parse_context(context)

        best_agent: str | None = None
        best_score = -1.0

        for agent_name in self._agents:
            s = self._score_agent(agent_name, ctx)
            if s > best_score:
                best_score = s
                best_agent = agent_name

        return best_agent


# ================================================================
# 4. AdaptiveRouter —— 自适应路由器
# ================================================================


@dataclass
class StrategyMetrics:
    """策略性能指标。"""
    total: int = 0
    success: int = 0
    confidence_sum: float = 0.0
    execution_time_sum: float = 0.0
    feedback_correct: int = 0
    feedback_total: int = 0

    @property
    def success_rate(self) -> float:
        return self.success / max(self.total, 1)

    @property
    def avg_confidence(self) -> float:
        return self.confidence_sum / max(self.total, 1)

    @property
    def avg_execution_time(self) -> float:
        return self.execution_time_sum / max(self.total, 1)

    @property
    def feedback_correct_rate(self) -> float:
        return self.feedback_correct / max(self.feedback_total, 1)


class AdaptiveRouter(IRoutingStrategy):
    """自适应路由器：动态权重调整 + 衰减因子 + 后备策略。

    包装多个子策略，根据历史表现动态计算权重，加权选择最优结果。
    权重公式：success_rate × 0.6 + avg_confidence × 0.2 + (1 - norm_time) × 0.1 + feedback_correct_rate × 0.1
    """

    # 权重公式系数
    W_SUCCESS = 0.6
    W_CONFIDENCE = 0.2
    W_SPEED = 0.1
    W_FEEDBACK = 0.1

    # 衰减因子：每次路由后旧策略权重 × DECAY，鼓励探索
    DECAY_FACTOR = 0.95

    def __init__(
        self,
        strategies: dict[str, IRoutingStrategy] | None = None,
    ) -> None:
        self._strategies: dict[str, IRoutingStrategy] = strategies or {}
        self._weights: dict[str, float] = {}
        self._metrics: dict[str, StrategyMetrics] = {}
        self._stale_counts: dict[str, int] = {}
        self._agents: dict[str, list[str]] = {}
        for name in self._strategies:
            self._weights.setdefault(name, 1.0)
            self._metrics.setdefault(name, StrategyMetrics())
            self._stale_counts.setdefault(name, 0)

    @property
    def strategy_names(self) -> list[str]:
        return list(self._strategies.keys())

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    # ---- 子策略管理 ----

    def add_sub_strategy(self, name: str, strategy: IRoutingStrategy) -> None:
        """添加子策略。"""
        self._strategies[name] = strategy
        if name not in self._weights:
            self._weights[name] = 1.0
            self._metrics[name] = StrategyMetrics()
            self._stale_counts[name] = 0
        for agent_name, capabilities in self._agents.items():
            strategy.add_agent(agent_name, capabilities)

    def add_agent(self, agent_name: str, capabilities: list[str]) -> None:
        self._agents[agent_name] = capabilities
        for strategy in self._strategies.values():
            strategy.add_agent(agent_name, capabilities)

    def remove_agent(self, agent_name: str) -> None:
        self._agents.pop(agent_name, None)
        for strategy in self._strategies.values():
            strategy.remove_agent(agent_name)

    def record_feedback(self, strategy_name: str, success: bool, confidence: float = 0.0,
                        execution_time_ms: float = 0.0) -> None:
        """反馈学习：更新策略性能指标。"""
        metrics = self._metrics.get(strategy_name)
        if metrics is None:
            return
        metrics.total += 1
        if success:
            metrics.success += 1
        metrics.confidence_sum += confidence
        metrics.execution_time_sum += execution_time_ms
        if success:
            metrics.feedback_correct += 1
        metrics.feedback_total += 1
        self._stale_counts[strategy_name] = 0

    # ---- 权重计算 ----

    def _normalize_time(self, time_ms: float, all_times: list[float]) -> float:
        """将执行时间归一化到 0-1（越小越接近 1）。"""
        if not all_times or max(all_times) == 0:
            return 0.5
        return 1.0 - (time_ms / max(all_times))

    def _compute_weights(self) -> dict[str, float]:
        """基于各策略性能指标计算动态权重。"""
        if not self._metrics:
            return {name: 1.0 for name in self._strategies}

        raw: dict[str, float] = {}
        all_times = [m.avg_execution_time for m in self._metrics.values()]

        for name in self._strategies:
            m = self._metrics.get(name)
            if not m or m.total == 0:
                raw[name] = 1.0
                continue

            sr = m.success_rate
            ac = m.avg_confidence
            sp = self._normalize_time(m.avg_execution_time, all_times)
            fc = m.feedback_correct_rate if m.feedback_total > 0 else 0.5

            raw[name] = (sr * self.W_SUCCESS + ac * self.W_CONFIDENCE
                         + sp * self.W_SPEED + fc * self.W_FEEDBACK)

        # 衰减调整
        for name in self._strategies:
            raw[name] *= (self.DECAY_FACTOR ** self._stale_counts.get(name, 0))

        # 归一化
        total = sum(raw.values())
        if total == 0:
            return {n: 1.0 / max(len(self._strategies), 1) for n in self._strategies}

        return {n: v / total for n, v in raw.items()}

    def _select_best_strategy(self) -> str | None:
        """按权重选择当前最优策略。"""
        weights = self._compute_weights()
        self._weights = weights
        if not weights:
            return None
        return max(weights, key=weights.get)

    # ---- 后备策略 ----

    def _fallback(self) -> str | None:
        """后备：所有子策略均未命中时，返回最后注册的智能体。"""
        if not self._agents:
            return None
        return list(self._agents.keys())[-1]

    def route(self, task_description: str, context: dict[str, Any]) -> str | None:
        if not self._strategies:
            return self._fallback()

        # 1. 选当前权重最高的策略
        best_strategy_name = self._select_best_strategy()
        if not best_strategy_name:
            return self._fallback()

        best_strategy = self._strategies.get(best_strategy_name)
        if not best_strategy:
            return self._fallback()

        # 2. 用选中的策略路由
        result = best_strategy.route(task_description, context)
        if result is not None:
            return result

        # 3. 主策略未命中 → 尝试其他策略
        for name, strategy in self._strategies.items():
            if name == best_strategy_name:
                continue
            result = strategy.route(task_description, context)
            if result is not None:
                return result

        # 4. 全部失败 → 后备
        return self._fallback()
