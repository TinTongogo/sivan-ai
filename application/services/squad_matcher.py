"""Squad 匹配器 — 根据任务描述和已路由智能体检测最佳匹配 Squad。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from infrastructure.persistence.shared_connection import _connect

logger = logging.getLogger(__name__)

# ── 匹配上下文 ────────────────────────────────────────

_MATCH_SCORE_ROUTED_AGENT = 3   # 路由到的 agent 属于该 squad
_MATCH_SCORE_KEYWORD_NAME = 2    # 关键词匹配 squad name/description
_MATCH_SCORE_KEYWORD_PHASE = 1   # 关键词匹配 phase name
_CONFIDENCE_THRESHOLD = 0.4      # 低于此阈值不匹配


@dataclass
class SquadMatch:
    """Squad 匹配结果。"""
    squad_id: str
    squad_name: str
    confidence: float       # 0-1
    match_reason: str       # 日志/展示用
    workflow_type: str = "sequential"
    phase_count: int = 0


def detect_squad(
    db_path: str | Path,
    task_description: str,
    routed_agent: str,
) -> SquadMatch | None:
    """检测任务描述是否匹配任何活跃 Squad。

    匹配策略：
      1. 任务关键词必须匹配 squad name/description 或 phase name（内容相关）
      2. routed_agent 属于该 squad → 加分
      3. 任务关键词匹配 squad name/description → 加分
      4. 任务关键词匹配阶段名称 → 加分
      综合打分归一化后与阈值比较。
    """
    try:
        conn = _connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT squad_id, name, description, workflow_type FROM squads WHERE status = 'active'"
        )
        squads = [dict(r) for r in cursor.fetchall()]
        if not squads:
            conn.close()
            return None

        task_lower = task_description.lower()
        # 提取英文词和中文词
        task_terms = set(
            w.strip().lower() for w in task_description.replace(",", " ").replace("，", " ").split()
            if len(w.strip()) > 1
        )

        best_match: tuple[str, float, str, str, int] = ("", 0.0, "", "", 0)

        for s in squads:
            sid = s["squad_id"]
            sname = s["name"] or ""
            sdesc = s["description"] or ""
            swf = s.get("workflow_type", "sequential")
            score = 0.0

            # 1. 查 routed_agent 是否属于该 squad
            cursor.execute(
                "SELECT agent_name FROM squad_agents WHERE squad_id = ?", (sid,)
            )
            squad_agents = {r["agent_name"] for r in cursor.fetchall()}
            agent_match = routed_agent in squad_agents

            # 2. 关键词匹配 squad name/description
            name_desc = (sname + " " + sdesc).lower()
            keyword_matches_name = any(term in name_desc for term in task_terms)

            # 3. 关键词匹配 phase 名称
            cursor.execute(
                "SELECT name FROM squad_workflows WHERE squad_id = ?", (sid,)
            )
            phase_names = [r["name"] or "" for r in cursor.fetchall()]
            keyword_matches_phase = any(
                term in pname.lower() for pname in phase_names for term in task_terms
            )

            # 必须有至少一项匹配（agent 归属 或 内容关键词）才继续
            if not agent_match and not keyword_matches_name and not keyword_matches_phase:
                continue

            if agent_match:
                score += _MATCH_SCORE_ROUTED_AGENT
            if keyword_matches_name:
                score += _MATCH_SCORE_KEYWORD_NAME
            if keyword_matches_phase:
                score += _MATCH_SCORE_KEYWORD_PHASE

            # 总分归一化（最大 6）
            max_possible = _MATCH_SCORE_ROUTED_AGENT + _MATCH_SCORE_KEYWORD_NAME + _MATCH_SCORE_KEYWORD_PHASE
            confidence = min(score / max_possible, 1.0) if max_possible > 0 else 0.0

            if confidence > best_match[1]:
                reason_parts = []
                if routed_agent in squad_agents:
                    reason_parts.append(f"智能体 {routed_agent} 属于该 Squad")
                if keyword_matches_name:
                    matched_terms = [t for t in task_terms if t in name_desc]
                    reason_parts.append(f"关键词匹配: {', '.join(matched_terms[:3])}")
                reason = "; ".join(reason_parts) if reason_parts else "综合匹配"
                best_match = (sid, confidence, sname, reason, len(phase_names))

        conn.close()

        sid, confidence, sname, reason, phase_count = best_match
        if confidence >= _CONFIDENCE_THRESHOLD:
            logger.info("Squad 匹配: %s (%s) — confidence=%.2f, reason=%s", sname, sid, confidence, reason)
            return SquadMatch(
                squad_id=sid,
                squad_name=sname,
                confidence=confidence,
                match_reason=reason,
                workflow_type=swf,
                phase_count=phase_count,
            )

        logger.debug("Squad 未匹配: best=%.2f < threshold=%.2f", confidence, _CONFIDENCE_THRESHOLD)
        return None

    except Exception as e:
        logger.warning("Squad 检测失败: %s", e)
        return None
