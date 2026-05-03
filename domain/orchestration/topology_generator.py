"""动态编排拓扑生成器。

根据任务特征动态生成最优编排拓扑。
生成策略（按优先级）：
1. 本能模板匹配 — 同等任务有过成功路径？直接复用
2. LLM 分析 — 分析任务特征，输出拓扑结构
3. 默认回退 — sequential 单阶段
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("sivan.topology")

# ── 五种编排模式触发条件 ──

_PATTERN_KEYWORDS: dict[str, list[str]] = {
    "sequential": [
        "pipeline", "step_by_step", "dependency_chain",
        "先", "再", "然后", "依次", "流程", "步骤",
    ],
    "parallel": [
        "independent_subtasks", "research", "data_collection",
        "同时", "并行", "分别", "各自", "独立",
    ],
    "conditional": [
        "decision_tree", "branching", "if_then_else",
        "如果", "否则", "分支", "条件", "取决于",
    ],
    "hierarchical": [
        "recursive", "nested_expertise", "sub_delegation",
        "分层", "递归", "嵌套", "深入",
    ],
    "consensus": [
        "high_stakes", "review", "validation",
        "安全", "合规", "审计", "评审", "审批", "共识",
    ],
}


class TopologyGenerator:
    """动态编排拓扑生成器。

    根据任务描述，结合本能模板和 LLM 分析，生成最优编排拓扑。
    """

    def __init__(self, instinct_repo=None, llm_analyzer=None) -> None:
        """
        Args:
            instinct_repo: InstinctRepository 实例（可选）
            llm_analyzer: LLM 分析函数（可选），签名 fn(task: str) -> dict
        """
        self._instinct_repo = instinct_repo
        self._llm_analyzer = llm_analyzer

    def generate(
        self,
        task_description: str,
        task_type: str = "general",
        task_signature: str = "",
    ) -> dict[str, Any]:
        """生成编排拓扑。

        策略优先级：
        1. 本能模板匹配
        2. LLM 分析
        3. 关键词规则回退

        Args:
            task_description: 任务描述文本
            task_type: 任务类型分类
            task_signature: 归一化任务特征（用于本能模板匹配）

        Returns:
            dict: {"phases": [...], "mode": "...", "reasoning": "..."}
        """
        # 策略 1: 本能模板匹配
        if self._instinct_repo and task_signature:
            try:
                pattern = self._instinct_repo.find_matching(task_type, task_signature)
                if pattern:
                    try:
                        topology = json.loads(pattern.topology_json)
                        topology["reasoning"] = f"本能模板匹配: {pattern.pattern_id} (置信度: {pattern.confidence:.2f})"
                        topology["from_instinct"] = True
                        logger.info("本能模板命中: %s (type=%s, confidence=%.2f)",
                                    pattern.pattern_id, task_type, pattern.confidence)
                        return topology
                    except (json.JSONDecodeError, TypeError):
                        pass
            except Exception as e:
                logger.warning("本能模板匹配失败: %s", e)

        # 策略 2: LLM 分析
        if self._llm_analyzer:
            try:
                result = self._llm_analyzer(task_description)
                if result and "phases" in result:
                    result["reasoning"] = result.get("reasoning", "LLM 分析生成")
                    result["from_instinct"] = False
                    return result
            except Exception as e:
                logger.warning("LLM 拓扑分析失败: %s", e)

        # 策略 3: 关键词规则回退
        return self._keyword_fallback(task_description)

    def _keyword_fallback(self, task_description: str) -> dict[str, Any]:
        """基于关键词的任务分析回退策略。"""
        task_lower = task_description.lower()

        # 检测编排模式
        mode_scores: dict[str, int] = {}
        for mode, keywords in _PATTERN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in task_lower)
            if score > 0:
                mode_scores[mode] = score

        if not mode_scores:
            # 默认单阶段 sequential
            return {
                "phases": [{"phase": 1, "mode": "sequential", "agents": [],
                           "description": "执行任务"}],
                "mode": "sequential",
                "reasoning": "默认回退: 单阶段执行",
                "from_instinct": False,
            }

        primary_mode = max(mode_scores, key=mode_scores.get)
        phases = self._build_default_phases(primary_mode)
        return {
            "phases": phases,
            "mode": primary_mode,
            "reasoning": f"关键词分析: 检测到 {primary_mode} 模式",
            "from_instinct": False,
        }

    @staticmethod
    def _build_default_phases(mode: str) -> list[dict[str, Any]]:
        """根据编排模式构建默认阶段。"""
        templates = {
            "sequential": [
                {"phase": 1, "mode": "sequential", "agents": [],
                 "description": "需求分析与规划"},
                {"phase": 2, "mode": "sequential", "agents": [],
                 "description": "执行实现"},
                {"phase": 3, "mode": "sequential", "agents": [],
                 "description": "审查与交付"},
            ],
            "parallel": [
                {"phase": 1, "mode": "sequential", "agents": [],
                 "description": "任务拆解与分配"},
                {"phase": 2, "mode": "parallel", "agents": [],
                 "description": "并行执行子任务"},
                {"phase": 3, "mode": "sequential", "agents": [],
                 "description": "结果汇总与审查"},
            ],
            "conditional": [
                {"phase": 1, "mode": "sequential", "agents": [],
                 "description": "信息收集与条件评估"},
                {"phase": 2, "mode": "conditional", "agents": [],
                 "description": "条件分支执行"},
                {"phase": 3, "mode": "sequential", "agents": [],
                 "description": "结果整合"},
            ],
            "hierarchical": [
                {"phase": 1, "mode": "sequential", "agents": [],
                 "description": "顶层架构规划"},
                {"phase": 2, "mode": "hierarchical", "agents": [],
                 "description": "逐层分解实现"},
                {"phase": 3, "mode": "consensus", "agents": [],
                 "description": "各层一致性审核"},
            ],
            "consensus": [
                {"phase": 1, "mode": "parallel", "agents": [],
                 "description": "独立评估"},
                {"phase": 2, "mode": "consensus", "agents": [],
                 "description": "共识会议"},
                {"phase": 3, "mode": "sequential", "agents": [],
                 "description": "最终决策输出"},
            ],
        }
        return templates.get(mode, templates["sequential"])

    @staticmethod
    def normalize_task_signature(task_description: str) -> str:
        """归一化任务特征，用于本能模板匹配。

        提取关键特征：领域关键词 + 任务类型 + 复杂度信号。
        """
        import re
        # 提取中英文关键词
        words = re.findall(r'[a-zA-Z0-9一-鿿]+', task_description.lower())
        # 去停用词
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
                      "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
                      "没有", "看", "好", "自己", "这", "他", "她", "它", "们"}
        keywords = [w for w in words if w not in stop_words and len(w) > 1]
        # 取前 10 个关键词作为签名
        return " ".join(keywords[:10])
