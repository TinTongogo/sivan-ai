"""智能体数据访问服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from interfaces.api.services.base import _connect


def get_agents_count(db_path: str | Path) -> dict[str, Any]:
    """获取智能体数量统计。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM agents")
        total = cursor.fetchone()["count"]
        cursor.execute("SELECT category, COUNT(*) as count FROM agents GROUP BY category")
        by_type = {r["category"]: r["count"] for r in cursor.fetchall()}
        conn.close()
        return {"total": total, "by_type": by_type}
    except Exception as e:
        return {"total": 0, "by_type": {}, "error": str(e)}


def get_agents_list(db_path: str | Path) -> list[dict[str, Any]]:
    """获取智能体列表。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT agent_id, display_name, description, category, status, version, created_at, updated_at "
            "FROM agents WHERE status = 'active' ORDER BY agent_id"
        )
        agents = []
        for row in cursor.fetchall():
            agents.append(
                {
                    "name": row["agent_id"],
                    "display_name": row["display_name"],
                    "description": row["description"] or "",
                    "category": row["category"],
                    "status": row["status"],
                    "version": row["version"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        conn.close()
        return agents
    except Exception as e:
        return [{"error": str(e)}]


def create_agent(db_path: str | Path, agent_data: dict[str, Any]) -> dict[str, Any]:
    """创建新智能体。"""
    try:
        required = ["name", "display_name", "description"]
        for field in required:
            if field not in agent_data or not agent_data[field]:
                return {"success": False, "error": f"缺少必填字段: {field}"}

        agent_id = agent_data["name"].strip().lower()
        display_name = agent_data["display_name"].strip()
        description = agent_data["description"].strip()
        category = agent_data.get("type", "domain")
        skills = agent_data.get("skills", [])

        if not agent_id.replace("-", "").isalnum():
            return {"success": False, "error": "智能体名称只能包含字母、数字和连字符"}

        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM agents WHERE agent_id = ?", (agent_id,))
        if cursor.fetchone()["cnt"] > 0:
            conn.close()
            return {"success": False, "error": f"智能体 '{agent_id}' 已存在"}

        skills_json = json.dumps(skills, ensure_ascii=False)
        tools_json = json.dumps(["read_file", "write_file", "edit_file", "bash"], ensure_ascii=False)
        system_prompt = (
            f"你是{display_name}，负责{description}。\n\n"
            f"核心职责：\n- 根据任务要求执行相关工作\n"
            f"- 遵循最佳实践和代码规范\n- 确保工作质量和可维护性\n\n"
            f"可用技能：{', '.join(skills) if skills else '暂无特定技能'}"
        )

        cursor.execute(
            "INSERT INTO agents (agent_id, display_name, description, category, skill_ids, tools, status, version, created_by, system_prompt, craft_declaration) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (agent_id, display_name, description, category, skills_json, tools_json, "active", 1, "admin_console",
             system_prompt,
             f"作为{display_name}，我致力于交付高质量、可维护的解决方案。"),
        )
        conn.commit()
        conn.close()
        return {
            "success": True, "message": f"智能体 '{agent_id}' 创建成功", "agent_id": agent_id,
            "display_name": display_name
        }
    except Exception as e:
        return {"success": False, "error": f"创建智能体失败: {str(e)}"}


def get_agent_detail(db_path: str | Path, agent_id: str) -> dict[str, Any] | None:
    """获取智能体详情。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None

        def safe_json(val, default=None):
            if not val:
                return default or []
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return default or []

        return {
            "agent_id": row["agent_id"],
            "display_name": row["display_name"],
            "description": row["description"] or "",
            "category": row["category"],
            "system_prompt": row["system_prompt"] or "",
            "craft_declaration": row["craft_declaration"] or "",
            "tools": safe_json(row["tools"]),
            "skill_ids": safe_json(row["skill_ids"]),
            "status": row["status"] or "active",
            "version": row["version"] or 1,
            "created_by": row["created_by"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    except Exception:
        return None


def update_agent(db_path: str | Path, agent_id: str, agent_data: dict[str, Any]) -> dict[str, Any]:
    """更新智能体。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM agents WHERE agent_id = ?", (agent_id,))
        if cursor.fetchone()["cnt"] == 0:
            conn.close()
            return {"success": False, "error": f"智能体 '{agent_id}' 不存在"}

        updates, params = [], []
        for field in ["display_name", "description", "category", "system_prompt",
                      "craft_declaration", "status"]:
            if field in agent_data:
                updates.append(f"{field} = ?")
                params.append(agent_data[field])
        for jf in ["tools", "skill_ids"]:
            if jf in agent_data:
                updates.append(f"{jf} = ?")
                params.append(json.dumps(agent_data[jf], ensure_ascii=False))
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            updates.append("version = version + 1")
            params.append(agent_id)
            cursor.execute(f"UPDATE agents SET {', '.join(updates)} WHERE agent_id = ?", params)
            conn.commit()
        conn.close()
        return {"success": True, "message": f"智能体 '{agent_id}' 更新成功"}
    except Exception as e:
        return {"success": False, "error": f"更新智能体失败: {str(e)}"}


def delete_agent(db_path: str | Path, agent_id: str) -> dict[str, Any]:
    """删除智能体。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM agents WHERE agent_id = ?", (agent_id,))
        if cursor.fetchone()["cnt"] == 0:
            conn.close()
            return {"success": False, "error": f"智能体 '{agent_id}' 不存在"}
        cursor.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"智能体 '{agent_id}' 已删除"}
    except Exception as e:
        return {"success": False, "error": f"删除智能体失败: {str(e)}"}
