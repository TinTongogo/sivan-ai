"""技能数据访问服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from interfaces.api.services.base import _connect


def get_skills_count(db_path: str | Path) -> dict[str, Any]:
    """获取技能数量统计。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM skills")
        total = cursor.fetchone()["total"]
        cursor.execute("SELECT category, COUNT(*) as count FROM skills WHERE category IS NOT NULL AND category != '' GROUP BY category")
        by_category = {r["category"]: r["count"] for r in cursor.fetchall()}
        cursor.execute(
            "SELECT SUM(usage_count) as total_usage, "
            "COUNT(CASE WHEN usage_count > 0 THEN 1 END) as used_skills, "
            "COUNT(CASE WHEN usage_count = 0 THEN 1 END) as unused_skills FROM skills"
        )
        usage_row = cursor.fetchone()
        conn.close()
        return {
            "total": total, "by_category": by_category,
            "usage": {"total_usage": usage_row["total_usage"] or 0, "used_skills": usage_row["used_skills"] or 0, "unused_skills": usage_row["unused_skills"] or 0},
        }
    except Exception as e:
        return {"total": 0, "by_category": {}, "usage": {"total_usage": 0, "used_skills": 0, "unused_skills": 0}, "error": str(e)}


def get_skills_list(db_path: str | Path) -> list[dict[str, Any]]:
    """获取技能列表。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT s.skill_id, s.name, s.display_name, s.description, s.argument_hint, s.allowed_tools, "
            "s.category, s.maintainer_agent, s.usage_count, s.last_used_at, s.created_at, s.updated_at, "
            "GROUP_CONCAT(DISTINCT st.tag) as tags "
            "FROM skills s LEFT JOIN skill_tags st ON s.skill_id = st.skill_id "
            "GROUP BY s.skill_id ORDER BY s.usage_count DESC, s.name ASC"
        )
        skills = [
            {"skill_id": r["skill_id"], "name": r["name"],
             "display_name": r["display_name"] or r["name"].replace("-", " ").title(),
             "description": r["description"], "argument_hint": r["argument_hint"],
             "allowed_tools": r["allowed_tools"], "category": r["category"],
             "maintainer_agent": r["maintainer_agent"], "usage_count": r["usage_count"],
             "last_used": r["last_used_at"], "created_at": r["created_at"], "updated_at": r["updated_at"],
             "tags": r["tags"].split(",") if r["tags"] else []}
            for r in cursor.fetchall()
        ]
        conn.close()
        return skills
    except Exception as e:
        return [{"error": str(e)}]


def get_skill_detail(db_path: str | Path, skill_id: str) -> dict[str, Any]:
    """获取技能详情。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT s.skill_id, s.name, s.display_name, s.description, s.content, "
            "s.argument_hint, s.allowed_tools, s.category, s.maintainer_agent, "
            "s.usage_count, s.last_used_at, s.created_at, s.updated_at, "
            "GROUP_CONCAT(DISTINCT st.tag) as tags "
            "FROM skills s LEFT JOIN skill_tags st ON s.skill_id = st.skill_id "
            "WHERE s.skill_id = ? GROUP BY s.skill_id",
            (skill_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"error": f"Skill not found: {skill_id}"}

        cursor.execute(
            "SELECT agent_name, timestamp, context_json FROM skill_usage WHERE skill_id = ? ORDER BY timestamp DESC LIMIT 10",
            (skill_id,),
        )
        usage_history = [{"agent_name": r["agent_name"], "timestamp": r["timestamp"], "context": r["context_json"]} for r in cursor.fetchall()]

        conn.close()
        return {
            "skill_id": row["skill_id"], "name": row["name"],
            "display_name": row["display_name"] or row["name"].replace("-", " ").title(),
            "description": row["description"], "content": row["content"],
            "argument_hint": row["argument_hint"], "allowed_tools": row["allowed_tools"],
            "category": row["category"], "maintainer_agent": row["maintainer_agent"],
            "usage_count": row["usage_count"], "last_used": row["last_used_at"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "metadata": {}, "usage_history": usage_history,
        }
    except Exception as e:
        return {"error": str(e)}


def get_skills_stats(db_path: str | Path) -> dict[str, Any]:
    """获取技能统计。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM skills")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT category, COUNT(*) as count FROM skills WHERE category IS NOT NULL AND category != '' GROUP BY category ORDER BY count DESC")
        by_category = {r["category"]: r["count"] for r in cursor.fetchall()}

        cursor.execute(
            "SELECT CASE WHEN usage_count = 0 THEN '未使用' WHEN usage_count <= 5 THEN '低频使用' "
            "WHEN usage_count <= 20 THEN '中频使用' ELSE '高频使用' END as frequency, "
            "COUNT(*) as count FROM skills GROUP BY frequency"
        )
        by_frequency = {r["frequency"]: r["count"] for r in cursor.fetchall()}

        cursor.execute("SELECT name, display_name, usage_count, last_used_at FROM skills ORDER BY usage_count DESC LIMIT 10")
        top_skills = [{"name": r["name"], "display_name": r["display_name"] or r["name"].replace("-", " ").title(), "usage_count": r["usage_count"], "last_used": r["last_used_at"]} for r in cursor.fetchall()]

        cursor.execute("SELECT name, display_name, last_used_at FROM skills WHERE last_used_at IS NOT NULL ORDER BY last_used_at DESC LIMIT 10")
        recent_skills = [{"name": r["name"], "display_name": r["display_name"] or r["name"].replace("-", " ").title(), "last_used": r["last_used_at"]} for r in cursor.fetchall()]

        conn.close()
        return {"total_skills": total, "by_category": by_category, "by_frequency": by_frequency, "top_skills": top_skills, "recent_skills": recent_skills}
    except Exception as e:
        return {"error": str(e)}


def get_skill_usage_trend(db_path: str | Path, range: str = "7d") -> list[dict[str, Any]]:
    """获取技能使用趋势。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        days = {"30d": 30, "90d": 90}.get(range, 7)
        cursor.execute(
            "SELECT DATE(DATETIME(timestamp, 'localtime')) as date, COUNT(*) as usage_count, COUNT(DISTINCT skill_id) as unique_skills, "
            "COUNT(DISTINCT agent_name) as unique_agents "
            "FROM skill_usage WHERE DATE(DATETIME(timestamp, 'localtime')) >= DATE('now', 'localtime', ?) GROUP BY DATE(DATETIME(timestamp, 'localtime')) ORDER BY date",
            (f"-{days} days",),
        )
        trend = [{"date": r["date"], "usage_count": r["usage_count"] or 0, "unique_skills": r["unique_skills"] or 0, "unique_agents": r["unique_agents"] or 0} for r in cursor.fetchall()]
        conn.close()
        return trend
    except Exception as e:
        return [{"error": str(e)}]


def get_agent_skill_usage(db_path: str | Path) -> dict[str, Any]:
    """获取Agent-Skill使用矩阵（合并运行时使用 + 配置关系）。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()

        # 1. 运行时使用数据
        cursor.execute(
            "SELECT su.agent_name, su.skill_id, s.name as skill_name, s.display_name as skill_display_name, "
            "s.category, COUNT(*) as usage_count, MAX(su.timestamp) as last_used "
            "FROM skill_usage su LEFT JOIN skills s ON su.skill_id = s.skill_id "
            "GROUP BY su.agent_name, su.skill_id ORDER BY su.agent_name, usage_count DESC"
        )
        matrix: dict[str, dict[str, dict]] = {}
        all_agents: set[str] = set()
        all_skills: set[str] = set()
        for row in cursor.fetchall():
            agent = row["agent_name"] or "unknown"
            skill_id = row["skill_id"]
            all_agents.add(agent)
            all_skills.add(skill_id)
            matrix.setdefault(agent, {})[skill_id] = {
                "skill_name": row["skill_name"] or skill_id,
                "skill_display_name": row["skill_display_name"] or skill_id,
                "category": row["category"],
                "usage_count": row["usage_count"] or 0,
                "last_used": row["last_used"],
            }

        # 2. 配置关系（agents.skill_ids）
        cursor.execute(
            "SELECT agent_id, display_name, skill_ids FROM agents WHERE status = 'active'"
        )
        configured_agents: dict[str, dict] = {}
        for row in cursor.fetchall():
            agent_id = row["agent_id"]
            display_name = row["display_name"] or agent_id
            all_agents.add(agent_id)
            raw = row["skill_ids"]
            configured_skills: list[str] = []
            if raw and raw.strip():
                try:
                    configured_skills = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    configured_skills = []
            configured_agents[agent_id] = {
                "display_name": display_name,
                "skill_ids": configured_skills,
            }
            # 确保已配置的技能出现在矩阵中（即使从未使用）
            for skill_id in configured_skills:
                all_skills.add(skill_id)
                if skill_id not in matrix.get(agent_id, {}):
                    matrix.setdefault(agent_id, {})[skill_id] = {
                        "skill_name": skill_id,
                        "skill_display_name": skill_id,
                        "category": None,
                        "usage_count": 0,
                        "last_used": None,
                    }

        # 3. 所有技能元数据
        cursor.execute("SELECT skill_id, name, display_name FROM skills WHERE status = 'active'")
        skill_meta = {r["skill_id"]: r for r in cursor.fetchall()}
        all_skills.update(skill_meta.keys())

        # 4. 标记 configured 字段 + 解析显示名
        for agent_id in all_agents:
            agent_cfg = configured_agents.get(agent_id, {})
            cfg_ids = agent_cfg.get("skill_ids", [])
            for skill_id in list(matrix.get(agent_id, {}).keys()):
                cell = matrix[agent_id][skill_id]
                cell["configured"] = skill_id in cfg_ids
                # 零使用且无显示名时从 skills 表补齐
                if cell.get("usage_count", 0) == 0 and cell["skill_name"] == skill_id:
                    meta = skill_meta.get(skill_id)
                    if meta:
                        cell["skill_name"] = meta["name"] or skill_id
                        cell["skill_display_name"] = meta["display_name"] or skill_id

        # 5. 技能聚合使用量（用于排序）
        cursor.execute(
            "SELECT skill_id, SUM(usage_count) as total_usage "
            "FROM skills WHERE usage_count > 0 GROUP BY skill_id ORDER BY total_usage DESC"
        )
        skill_totals = {r["skill_id"]: r["total_usage"] or 0 for r in cursor.fetchall()}

        conn.close()
        return {
            "agents": sorted(all_agents),
            "skills": sorted(all_skills),
            "matrix": matrix,
            "skill_totals": skill_totals,
            "configured_agents": configured_agents,
        }
    except Exception as e:
        return {"error": str(e)}


def update_skill(db_path: str | Path, skill_id: str, skill_data: dict[str, Any]) -> dict[str, Any]:
    """更新技能。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM skills WHERE skill_id = ?", (skill_id,))
        if cursor.fetchone()["cnt"] == 0:
            conn.close()
            return {"success": False, "error": f"技能 '{skill_id}' 不存在"}
        updates, params = [], []
        for field in ["name", "display_name", "description", "category", "maintainer_agent", "argument_hint", "allowed_tools", "content"]:
            if field in skill_data:
                updates.append(f"{field} = ?")
                params.append(skill_data[field])
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(skill_id)
            cursor.execute(f"UPDATE skills SET {', '.join(updates)} WHERE skill_id = ?", params)
            conn.commit()
        conn.close()
        return {"success": True, "message": f"技能 '{skill_id}' 更新成功"}
    except Exception as e:
        return {"success": False, "error": f"更新技能失败: {str(e)}"}


def delete_skill(db_path: str | Path, skill_id: str) -> dict[str, Any]:
    """删除技能。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM skills WHERE skill_id = ?", (skill_id,))
        if cursor.fetchone()["cnt"] == 0:
            conn.close()
            return {"success": False, "error": f"技能 '{skill_id}' 不存在"}
        cursor.execute("DELETE FROM skill_tags WHERE skill_id = ?", (skill_id,))
        cursor.execute("DELETE FROM skill_usage WHERE skill_id = ?", (skill_id,))
        cursor.execute("DELETE FROM skills WHERE skill_id = ?", (skill_id,))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"技能 '{skill_id}' 已删除"}
    except Exception as e:
        return {"success": False, "error": f"删除技能失败: {str(e)}"}


def check_skill_archiving(db_path: str | Path):
    """技能归档检查：连续30天无调用标记为 observing。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT skill_id, name, maintainer_agent, last_used_at FROM skills "
            "WHERE status = 'active' AND last_used_at IS NOT NULL AND julianday('now') - julianday(last_used_at) > 30"
        )
        stale = cursor.fetchall()
        for sk in stale:
            cursor.execute("UPDATE skills SET status = 'observing', updated_at = CURRENT_TIMESTAMP WHERE skill_id = ?", (sk["skill_id"],))
        conn.commit()
        conn.close()
        if stale:
            print(f"[Skill] 本次归档 {len(stale)} 个技能")
    except Exception as e:
        print(f"[Skill] 技能归档检查失败: {e}")
