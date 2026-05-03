"""契约数据访问服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from interfaces.api.services.base import _connect


def get_contracts_count(db_path: str | Path) -> dict[str, Any]:
    """获取契约数量统计。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM contracts")
        total = cursor.fetchone()["count"]
        cursor.execute("SELECT contract_type, COUNT(*) as count FROM contracts GROUP BY contract_type")
        by_type = {r["contract_type"]: r["count"] for r in cursor.fetchall()}
        cursor.execute("SELECT status, COUNT(*) as count FROM contracts GROUP BY status")
        by_status = {r["status"]: r["count"] for r in cursor.fetchall()}
        conn.close()
        return {"total": total, "by_type": by_type, "by_status": by_status}
    except Exception as e:
        return {"total": 0, "by_type": {}, "by_status": {}, "error": str(e)}


def get_contracts_list(db_path: str | Path) -> list[dict[str, Any]]:
    """获取契约列表。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.contract_id, c.contract_type, c.content_json, c.created_by, c.created_at, c.updated_at, c.status, c.version, GROUP_CONCAT(DISTINCT t.tag) as tags "
            "FROM contracts c LEFT JOIN contract_tags t ON c.contract_id = t.contract_id "
            "GROUP BY c.contract_id ORDER BY c.created_at DESC LIMIT 50"
        )
        contracts = []
        for row in cursor.fetchall():
            content = json.loads(row["content_json"]) if row["content_json"] else {}
            tags = row["tags"].split(",") if row["tags"] else []
            contracts.append({
                "contract_id": row["contract_id"],
                "contract_type": row["contract_type"],
                "content": content,
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "status": row["status"],
                "version": row["version"],
                "tags": tags,
            })
        conn.close()
        return contracts
    except Exception as e:
        return [{"error": str(e)}]


def get_contract_detail(db_path: str | Path, contract_id: str) -> dict[str, Any]:
    """获取契约详情。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.contract_id, c.contract_type, c.content_json, c.created_by, c.created_at, c.updated_at, c.version, c.status, "
            "GROUP_CONCAT(DISTINCT t.tag) as tags, GROUP_CONCAT(DISTINCT d.depends_on_contract_id) as dependencies "
            "FROM contracts c LEFT JOIN contract_tags t ON c.contract_id = t.contract_id "
            "LEFT JOIN contract_dependencies d ON c.contract_id = d.contract_id "
            "WHERE c.contract_id = ? GROUP BY c.contract_id",
            (contract_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {"error": "Contract not found"}

        content = json.loads(row["content_json"]) if row["content_json"] else {}
        return {
            "contract_id": row["contract_id"],
            "contract_type": row["contract_type"],
            "content": content,
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version": row["version"],
            "status": row["status"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "dependencies": row["dependencies"].split(",") if row["dependencies"] else [],
        }
    except Exception as e:
        return {"error": str(e)}


def delete_contract(db_path: str | Path, contract_id: str) -> bool:
    """删除单个契约。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contract_tags WHERE contract_id = ?", (contract_id,))
        cursor.execute("DELETE FROM contract_dependencies WHERE contract_id = ? OR depends_on_contract_id = ?",
                       (contract_id, contract_id))
        cursor.execute("DELETE FROM contract_versions WHERE contract_id = ?", (contract_id,))
        cursor.execute("DELETE FROM contracts WHERE contract_id = ?", (contract_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    except Exception:
        return False


def delete_contracts_batch(db_path: str | Path, contract_ids: list[str]) -> dict[str, Any]:
    """批量删除契约。"""
    deleted = 0
    for cid in contract_ids:
        if delete_contract(db_path, cid):
            deleted += 1
    return {"success": True, "deleted": deleted}


def get_contract_graph(db_path: str | Path) -> dict[str, Any]:
    """获取契约依赖关系图数据。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.contract_id, c.contract_type, c.status, c.created_by, c.content_json, "
            "GROUP_CONCAT(DISTINCT d.depends_on_contract_id) as deps "
            "FROM contracts c LEFT JOIN contract_dependencies d ON c.contract_id = d.contract_id "
            "GROUP BY c.contract_id ORDER BY c.contract_type"
        )
        nodes, edges, node_ids = [], [], set()
        for row in cursor.fetchall():
            cid = row["contract_id"]
            content = json.loads(row["content_json"]) if row["content_json"] else {}
            title = content.get("title", cid[:16])
            nodes.append({
                "id": cid, "label": title[:20],
                "title": f"{title}\n类型: {row['contract_type']}\n状态: {row['status']}\n创建者: {row['created_by']}",
                "group": row["contract_type"], "status": row["status"],
            })
            node_ids.add(cid)
            deps = row["deps"].split(",") if row["deps"] else []
            for dep in deps:
                dep = dep.strip()
                if dep:
                    edges.append({"from": cid, "to": dep, "arrows": "to", "dashes": False})
                    if dep not in node_ids:
                        node_ids.add(dep)
        conn.close()
        return {
            "nodes": nodes, "edges": edges,
            "legend": {
                "global": {"label": "全局契约", "color": "#4e73df"},
                "api": {"label": "API契约", "color": "#1cc88a"},
                "ui": {"label": "UI契约", "color": "#36b9cc"},
                "data": {"label": "数据契约", "color": "#f6c23e"},
                "model": {"label": "模型契约", "color": "#858796"},
            },
        }
    except Exception as e:
        return {"error": str(e), "nodes": [], "edges": []}
