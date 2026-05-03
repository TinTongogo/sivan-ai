"""AgentResolver — 动态编排时解析 LLM 生成的 agent 名称到真实注册表。

使用场景：
  Orchestrator 返回 squad 拓扑后，execute_dynamic_squad 调用
  resolve_topology()，将拓扑中可能不存在的 agent 名称映射到
  已注册的 18 个智能体，彻底无匹配时才自动创建新智能体。
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("sivan.agent_resolver")

# 模糊匹配阈值，低于此值返回 None（触发创建）
AUTO_MATCH_THRESHOLD = 0.40

# 常用缩写映射 + 英文→中文桥接，用于 description 语义匹配
_ABBREVIATIONS: dict[str, str] = {
    # 英文缩写 ↔ 全称
    "fe": "frontend",
    "be": "backend",
    "dev": "developer",
    "ui": "userinterface",
    "ux": "userexperience",
    "ml": "machinelearning",
    "ops": "operations",
    "sec": "security",
    "db": "database",
    "admin": "administrator",
    "eng": "engineering",
    "qa": "qualityassurance",
    "po": "productowner",
    "de": "dataengineer",
    # 英文 role term → description 中出现的 Chinese term
    "frontend": "前端",
    "backend": "后端",
    "engineer": "工程师",
    "developer": "工程师",
    "data": "数据",
    "mobile": "移动端",
    "security": "安全",
    "vision": "视觉",
    "speech": "语音",
    "inference": "推理",
    "model": "模型",
    "expert": "专家",
    "designer": "设计师",
    "design": "设计",
    "quality": "质量",
    "product": "产品",
    "owner": "负责人",
    "architect": "架构师",
    "orchestrator": "协调",
    "computer": "计算机",
    "edge": "端侧",
    # 传递展开链 (abbreviation → full → Chinese)
    "qualityassurance": "质量",
    "productowner": "产品",
    "userinterface": "界面",
    "dataengineer": "数据",
    "userexperience": "体验",
    "machinelearning": "机器学习",
    "operations": "运维",
    "engineering": "工程",
    "administrator": "管理员",
}

# _ABBREVIATIONS 中所有 key 和 value 的并集，用于判定 term 是否"已知"
_KNOWN_TERMS: set[str] = set(_ABBREVIATIONS.keys()) | set(_ABBREVIATIONS.values())

# Agent 创建防护：以下泛称 token 不能作为唯一领域词
_GENERIC_ROLE_TOKENS: set[str] = {
    # 角色泛称
    "engineer", "developer", "expert", "specialist", "professional",
    "architect", "designer", "manager", "coordinator", "assistant",
    "helper", "analyst", "scientist", "researcher", "consultant",
    # 职级 / 修饰
    "senior", "junior", "lead", "principal", "staff", "associate",
    "intern", "entry", "mid", "chief", "head",
    # 流行词
    "guru", "ninja", "rockstar",
}

# Skill 创建防护泛称
_GENERIC_SKILL_TOKENS: set[str] = {
    "skill", "task", "job", "work", "function", "utility",
    "helper", "tool", "service", "module", "plugin",
    "my", "your", "basic", "simple", "new", "custom", "demo",
}

# 重叠检查阈值：特异性 token 在现有 agent description 中的 score 低于此值才允许创建
CREATE_OVERLAP_THRESHOLD = 0.15


class AgentResolver:
    """拓扑 agent 名称解析器。

    用法：
        resolver = AgentResolver(db_path)
        resolved = resolver.resolve_topology(topology)
        phases = resolved["phases"]
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._agents: dict[str, dict[str, Any]] = {}
        self._skills: dict[str, dict[str, Any]] = {}
        self._agent_repo: Any = None
        self._idf: dict[str, float] = {}
        self._idf_default: float = 0.0
        self._load_registry()

    # ── 公开接口 ────────────────────────────────────────────────

    def resolve_topology(self, topology: dict) -> dict:
        """解析拓扑中所有 agent 名称。"""
        for phase in topology.get("phases", []):
            resolved_agents = []
            for agent_name in phase.get("agents", []):
                rid = self.resolve_agent(agent_name)
                if rid:
                    resolved_agents.append(rid)
                    logger.info("AgentResolver: '%s' → '%s'", agent_name, rid)
                else:
                    if self._should_create_agent(agent_name):
                        new_id = self.create_agent(agent_name)
                        resolved_agents.append(new_id)
                        logger.info("AgentResolver: 创建智能体 '%s' ← '%s'", new_id, agent_name)
                    else:
                        logger.info("AgentResolver: 跳过 '%s' — 不满足创建条件", agent_name)
            phase["agents"] = resolved_agents

            if "skills" in phase:
                resolved_skills = []
                for skill_name in phase["skills"]:
                    rid = self.resolve_skill(skill_name)
                    if rid:
                        resolved_skills.append(rid)
                    else:
                        if self._should_create_skill(skill_name):
                            new_id = self.create_skill(skill_name)
                            resolved_skills.append(new_id)
                        else:
                            logger.info("AgentResolver: 跳过 skill '%s' — 不满足创建条件", skill_name)
                phase["skills"] = resolved_skills

        topology["_resolved_by"] = "AgentResolver"
        return topology

    def resolve_agent(self, name: str) -> str | None:
        """将 agent 名称解析为已注册的 agent_id，无匹配返回 None。"""
        # 1) 精确匹配
        if name in self._agents:
            return name

        # 2) 归一化匹配
        norm = self._normalize(name)
        for aid in self._agents:
            if self._normalize(aid) == norm:
                return aid
        for aid, info in self._agents.items():
            if self._normalize(info.get("display_name", "")) == norm:
                return aid

        # 3) 描述匹配：LLM 决策的角色名 → agent.description 语义匹配
        if self._is_name_vague(name):
            return None  # 过于模糊，不匹配任何现有智能体

        query_tokens = self._tokenize(name)
        best_id: str | None = None
        best_score = 0.0
        best_tie = -1
        for aid, info in self._agents.items():
            score = self._description_score(query_tokens, info.get("description", ""))
            if score > best_score:
                best_score = score
                best_id = aid
                best_tie = self._tiebreak_score(query_tokens, aid)
            elif score == best_score and score > 0 and best_id is not None:
                tb = self._tiebreak_score(query_tokens, aid)
                if tb > best_tie:
                    best_id = aid
                    best_tie = tb

        if best_score >= AUTO_MATCH_THRESHOLD:
            return best_id
        return None

    def resolve_skill(self, name: str) -> str | None:
        """将技能名称解析为已注册的 skill_id。"""
        if name in self._skills:
            return name

        norm = self._normalize(name)
        for sid, info in self._skills.items():
            if self._normalize(sid) == norm:
                return sid
            if self._normalize(info.get("name", "")) == norm:
                return sid
            if self._normalize(info.get("display_name", "")) == norm:
                return sid

        query_tokens = self._tokenize(name)
        best_id: str | None = None
        best_score = 0.0
        for sid, info in self._skills.items():
            target_tokens = (
                self._tokenize(sid)
                | self._tokenize(info.get("name", ""))
                | self._tokenize(info.get("description", ""))
            )
            if not target_tokens:
                continue
            score = len(query_tokens & target_tokens) / len(target_tokens)
            if score > best_score:
                best_score = score
                best_id = sid

        return best_id if best_score >= AUTO_MATCH_THRESHOLD else None

    def create_agent(self, agent_name: str) -> str:
        """创建新智能体并热加载，返回 agent_id。"""
        agent_id = self._slugify(agent_name)
        display_name = agent_name.replace("-", " ").replace("_", " ").title()

        # 动态匹配与 agent 职责相关的技能（防止超级单体，仅加载 top-k）
        matched_skills = self._pick_skills_for_agent(agent_name, top_k=6)

        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            # 去重
            cursor.execute("SELECT COUNT(*) FROM agents WHERE agent_id = ?", (agent_id,))
            if cursor.fetchone()[0] > 0:
                agent_id = f"{agent_id}-{uuid.uuid4().hex[:4]}"

            skill_ids_json = json.dumps(matched_skills)
            description = f"由编排器自动创建: {agent_name}"
            system_prompt = (
                f"你是 {display_name}，由 Sivan 系统自动创建的智能体。\n\n"
                f"你的任务是根据用户描述提供专业帮助。\n\n"
                f"行为准则：\n"
                f"1. 直接回答问题，提供清晰、有价值的输出\n"
                f"2. 如果不确定，诚实地说明局限性\n"
                f"3. 保持专业、简洁的回复风格\n"
            )

            cursor.execute(
                """INSERT INTO agents
                   (agent_id, display_name, description, category,
                    system_prompt, craft_declaration,
                    tools, skill_ids,
                    version, status, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    agent_id, display_name, description, "auto-created",
                    system_prompt, "",
                    "[]", skill_ids_json,
                    "1.0.0", "active", "agent_resolver",
                ),
            )
            conn.commit()
        finally:
            conn.close()

        self._reload_agent(agent_id)
        # 同步到内存缓存
        self._load_registry()
        return agent_id

    def create_skill(self, skill_name: str) -> str:
        """创建新技能，返回 skill_id。"""
        skill_id = self._slugify(skill_name)
        name = skill_name.replace("-", " ").replace("_", " ").title()

        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM skills WHERE skill_id = ?", (skill_id,))
            if cursor.fetchone()[0] > 0:
                skill_id = f"{skill_id}-{uuid.uuid4().hex[:4]}"

            description = f"由编排器自动创建: {skill_name}"
            content = f"# {name}\n\n由编排器自动创建的技能。\n"

            cursor.execute(
                """INSERT INTO skills
                   (skill_id, name, display_name, description, content,
                    argument_hint, allowed_tools, category, status, maintainer_agent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (skill_id, name, name, description, content,
                 "", "", "auto-created", "active", None),
            )
            conn.commit()
        finally:
            conn.close()

        self._load_registry()
        return skill_id

    # ── 内部方法 ────────────────────────────────────────────────

    def _load_registry(self) -> None:
        """从 DB 加载所有活跃智能体和技能到内存缓存。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()

            self._agents = {}
            cursor.execute("SELECT * FROM agents WHERE status = 'active'")
            for row in cursor.fetchall():
                d = dict(row)
                aid = d["agent_id"]
                self._agents[aid] = {
                    "display_name": d.get("display_name", ""),
                    "description": d.get("description") or "",
                    "skill_ids": json.loads(d["skill_ids"]) if d.get("skill_ids") else [],
                }

            self._skills = {}
            cursor.execute("SELECT * FROM skills WHERE status = 'active'")
            for row in cursor.fetchall():
                d = dict(row)
                sid = d["skill_id"]
                self._skills[sid] = {
                    "name": d.get("name", ""),
                    "display_name": d.get("display_name") or d.get("name", ""),
                    "description": d.get("description") or "",
                    "category": d.get("category") or "",
                }

            # 计算 IDF：_ABBREVIATIONS 中所有 term 在多少条 agent description 中出现
            # 用于描述匹配时降低高频词（工程师）权重、提升特征词（后端）权重
            # 不在任何 description 中出现的 term → IDF = 0（不贡献分子分母）
            n = len(self._agents)
            all_terms = set(_ABBREVIATIONS.keys()) | set(_ABBREVIATIONS.values())
            token_df: dict[str, int] = {}
            for info in self._agents.values():
                desc = info["description"]
                for t in all_terms:
                    if self._term_in_desc(t, desc):
                        token_df[t] = token_df.get(t, 0) + 1
            self._idf = {t: math.log(n / df) for t, df in token_df.items()}
            self._idf_default = 0.0  # 不在任何 desc 中的 term 不参与评分

        finally:
            conn.close()

    def _reload_agent(self, agent_id: str) -> None:
        """热加载智能体到 AgentRepository 内存。"""
        try:
            if self._agent_repo is None:
                from infrastructure.persistence.agent_repo import AgentRepository
                from infrastructure.persistence.connection import SQLiteConnectionManager
                cm = SQLiteConnectionManager(str(self._db_path))
                self._agent_repo = AgentRepository(cm)
            self._agent_repo.reload(agent_id)
        except Exception as exc:
            logger.warning("AgentResolver reload(%s) 失败: %s", agent_id, exc)

    @staticmethod
    def _normalize(s: str) -> str:
        """去连字符/下划线/空格，转小写。"""
        return re.sub(r"[\s\-_]+", "", s).lower()

    @staticmethod
    def _tokenize(s: str) -> set[str]:
        """按连字符/下划线/空格/驼峰拆分，过滤单字。"""
        s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
        tokens = set(re.findall(r"[a-zA-Z0-9一-鿿]{2,}", s.lower()))
        return tokens

    @staticmethod
    def _expand_tokens(tokens: set[str]) -> set[str]:
        """BFS 传递展开缩写/翻译链，如 qa → qualityassurance → 质量。"""
        expanded = set(tokens)
        queue = list(tokens)
        while queue:
            t = queue.pop()
            if t in _ABBREVIATIONS:
                v = _ABBREVIATIONS[t]
                if v not in expanded:
                    expanded.add(v)
                    queue.append(v)
            for abbr, full in _ABBREVIATIONS.items():
                if t == full and abbr not in expanded:
                    expanded.add(abbr)
                    queue.append(abbr)
        return expanded

    @staticmethod
    def _slugify(name: str) -> str:
        """转为 agent_id 兼容的 slug 格式。"""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9一-鿿]+", "-", slug)
        return slug.strip("-") or "auto-agent"

    @staticmethod
    def _term_in_desc(term: str, description: str) -> bool:
        """检查 term 是否在 description 中出现。

        英文 term 用 \\bword\\b 词边界匹配防止误配（如 dev 不匹配 devops），
        中文 term 用子串匹配（CJK 字符天然是原子单位）。
        """
        if not description:
            return False
        if re.match(r'^[a-zA-Z]', term):
            return bool(re.search(r'\b' + re.escape(term) + r'\b', description.lower()))
        return term in description

    def _description_score(self, query_tokens: set[str], description: str) -> float:
        """IDF 加权 query 在 description 中的覆盖率。

        不在 _ABBREVIATIONS 中的 term（如 blockchain）→ 权重 ln(N) 惩罚未知概念，
        在 _ABBREVIATIONS 中但不匹配任何 description（如英文形式）→ 权重 0，
        在 _ABBREVIATIONS 中且匹配 description（如中文翻译）→ 权重 IDF。
        """
        expanded = self._expand_tokens(query_tokens)
        matched = {t for t in expanded if self._term_in_desc(t, description)}
        if not matched:
            return 0.0

        idf = self._idf
        n = len(self._agents)
        penalty = math.log(n) if n > 0 else 0.0

        total_w = 0.0
        matched_w = 0.0
        for t in expanded:
            if t in idf:
                w = idf[t]
            elif t in _KNOWN_TERMS:
                w = 0.0
            else:
                w = penalty
            total_w += w
            if t in matched:
                matched_w += w

        return matched_w / total_w if total_w > 0 else 0.0

    @staticmethod
    def _tiebreak_score(query_tokens: set[str], agent_id: str) -> int:
        """description 分数相同时，用 expanded query 与 expanded agent_id 的重叠数破平。"""
        qe = AgentResolver._expand_tokens(query_tokens)
        ae = AgentResolver._expand_tokens(AgentResolver._tokenize(agent_id))
        return len(qe & ae)

    # ── 创建防护 ────────────────────────────────────────────────

    @staticmethod
    def _is_name_vague(name: str) -> bool:
        """检查角色名是否过于模糊（仅含泛称 token，缺乏领域特异性）。"""
        tokens = AgentResolver._tokenize(name)
        specific = tokens - _GENERIC_ROLE_TOKENS
        return len(specific) == 0

    @staticmethod
    def _is_skill_vague(name: str) -> bool:
        """检查技能名是否过于模糊。"""
        tokens = AgentResolver._tokenize(name)
        specific = tokens - _GENERIC_SKILL_TOKENS
        return len(specific) == 0

    def _is_role_covered(self, name: str) -> bool:
        """检查角色是否已被现有智能体覆盖（SRP 保护）。

        使用非泛称 token 对现有 agent description 做 description_score，
        高于阈值说明职责已存在，创建会违反单一职责原则。
        """
        tokens = self._tokenize(name)
        specific = tokens - _GENERIC_ROLE_TOKENS
        if not specific:
            return False  # 已被 _is_name_vague 拦截
        for info in self._agents.values():
            score = self._description_score(specific, info.get("description", ""))
            if score >= CREATE_OVERLAP_THRESHOLD:
                return True
        return False

    def _should_create_agent(self, name: str) -> bool:
        """宁缺毋滥：检查是否应该为 name 创建新智能体。

        必须同时满足：
        1. 角色名有领域特异性（非纯泛称）
        2. 角色未被现有智能体覆盖（SRP）
        """
        if self._is_name_vague(name):
            logger.warning("AgentResolver: 拒绝创建 '%s' — 角色名过于模糊", name)
            return False
        if self._is_role_covered(name):
            logger.warning("AgentResolver: 拒绝创建 '%s' — 与现有智能体重叠", name)
            return False
        return True

    def _should_create_skill(self, name: str) -> bool:
        """检查是否应该为 name 创建新技能。"""
        if self._is_skill_vague(name):
            logger.warning("AgentResolver: 拒绝创建 skill '%s' — 名称过于模糊", name)
            return False
        return True

    def _pick_skills_for_agent(self, agent_name: str, top_k: int = 6) -> list[str]:
        """根据 agent 角色名，动态匹配最合适的技能。

        策略（防止 agent+skill 滥用成为超级单体）：
        1. 用 description_score 找最相似的现有 agent
        2. 继承其技能作为基础（同类 agent 做同类事，技能自然共享）
        3. top_k 限制防止一个 agent 挂载过多技能

        示例：backend-engineer → 相似 be-dev (score=1.000)
          → 继承: ddd-modeling, api-design, security-hardening, ...
        """
        query_tokens = self._tokenize(agent_name)
        if not query_tokens:
            return []

        # 1) 找最相似 agent → 继承其技能（用 _tiebreak_score 破平）
        best_aid = None
        best_score = 0.0
        best_tie = -1
        for aid, info in self._agents.items():
            score = self._description_score(query_tokens, info.get("description", ""))
            if score > best_score:
                best_score = score
                best_aid = aid
                best_tie = self._tiebreak_score(query_tokens, aid)
            elif score == best_score and score > 0 and best_aid is not None:
                tb = self._tiebreak_score(query_tokens, aid)
                if tb > best_tie:
                    best_aid = aid
                    best_tie = tb

        # 2) 继承技能
        inherited: list[str] = []
        if best_aid and best_score > 0:
            inherited = list(self._agents[best_aid].get("skill_ids", []))

        # 3) 低相似度时尝试用展开 token 直接匹配 skill name/description 作为补充
        if best_score < 0.40:
            expanded = self._expand_tokens(query_tokens)
            for sid, info in self._skills.items():
                if len(inherited) >= top_k:
                    break
                if sid in inherited:
                    continue
                target = f"{info.get('name', '')} {info.get('description', '')}"
                target_tokens = self._tokenize(target)
                if target_tokens and (expanded & target_tokens):
                    inherited.append(sid)

        return inherited[:top_k]
