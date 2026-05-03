"""契约仓库 SQLite 实现。

基于现有 DatabaseContractManager 实现 IContractRepository 接口。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from domain.contract.repository import IContractRepository
from infrastructure.persistence.connection import SQLiteConnectionManager


class ContractRepository(IContractRepository):
    """基于 SQLite 的契约仓库。"""

    def __init__(self, connection_manager: SQLiteConnectionManager) -> None:
        self._db = connection_manager
        self._init_tables()

    def _init_tables(self) -> None:
        pass  # schema 由 Alembic 管理

    def create(
        self,
        contract_type: str,
        content: dict[str, Any],
        created_by: str,
    ) -> str:
        now = datetime.now().isoformat()
        contract_id = str(uuid.uuid4())[:8]

        # Extract metadata
        tags = content.pop("tags", []) if isinstance(content, dict) else []
        dependencies = content.pop("dependencies", []) if isinstance(content, dict) else []
        metadata = content.pop("metadata", None) if isinstance(content, dict) else None
        status = content.pop("status", "draft") if isinstance(content, dict) else "draft"

        # Auto-generate title if missing
        if isinstance(content, dict) and not content.get("title"):
            title = (content.get("name") or "")[:60]
            if not title:
                title = (content.get("description") or "")[:30]
            if not title:
                title = f"{contract_type}契约 {now[:10]}"
            content["title"] = title

        self._db.execute(
            """INSERT INTO contracts
               (contract_id, contract_type, content_json, created_by,
                created_at, updated_at, status, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                contract_id,
                contract_type,
                json.dumps(content, ensure_ascii=False),
                created_by,
                now,
                now,
                status,
                json.dumps(metadata, ensure_ascii=False) if metadata else None,
            ),
        )

        for tag in tags if isinstance(tags, list) else []:
            self._db.execute(
                "INSERT OR IGNORE INTO contract_tags (contract_id, tag) VALUES (?, ?)",
                (contract_id, tag),
            )

        for dep in dependencies if isinstance(dependencies, list) else []:
            self._db.execute(
                "INSERT OR IGNORE INTO contract_dependencies (contract_id, depends_on_contract_id) VALUES (?, ?)",
                (contract_id, dep),
            )

        self._db.execute(
            """INSERT INTO contract_versions
               (contract_id, version, content_json, created_by, change_description)
               VALUES (?, '1.0.0', ?, ?, '初始创建')""",
            (contract_id, json.dumps(content, ensure_ascii=False), created_by),
        )

        self._db.commit()
        return contract_id

    def find_by_id(self, contract_id: str) -> dict[str, Any] | None:
        row = self._db.execute(
            "SELECT * FROM contracts WHERE contract_id=?",
            (contract_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def update(self, contract_id: str, updates: dict[str, Any]) -> bool:
        existing = self.find_by_id(contract_id)
        if not existing:
            return False

        now = datetime.now().isoformat()

        if "content" in updates:
            updates["content_json"] = json.dumps(
                updates.pop("content"), ensure_ascii=False
            )
        if "status" in updates:
            updates["status"] = updates["status"]
        if "metadata" in updates:
            updates["metadata_json"] = json.dumps(
                updates.pop("metadata"), ensure_ascii=False
            )

        updates["updated_at"] = now
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [contract_id]

        self._db.execute(
            f"UPDATE contracts SET {set_clause} WHERE contract_id=?",
            tuple(values),
        )

        # Record version history if content changed
        if "content_json" in updates:
            old_ver = existing.get("version", "1.0.0")
            new_ver = self._bump_version(old_ver)
            self._db.execute(
                "UPDATE contracts SET version=? WHERE contract_id=?",
                (new_ver, contract_id),
            )
            self._db.execute(
                """INSERT INTO contract_versions
                   (contract_id, version, content_json, created_by, change_description)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    contract_id,
                    new_ver,
                    updates["content_json"],
                    existing.get("created_by", "system"),
                    "内容更新",
                ),
            )

        self._db.commit()
        return True

    def find(
        self,
        contract_type: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = ["1=1"]
        params: list[Any] = []

        if contract_type:
            conditions.append("c.contract_type=?")
            params.append(contract_type)
        if status:
            conditions.append("c.status=?")
            params.append(status)
        if tag:
            conditions.append("ct.tag=?")
            params.append(tag)

        join_clause = ""
        if tag:
            join_clause = "JOIN contract_tags ct ON c.contract_id = ct.contract_id"

        rows = self._db.execute(
            f"SELECT DISTINCT c.* FROM contracts c {join_clause} "
            f"WHERE {' AND '.join(conditions)} ORDER BY c.created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()

        return [self._row_to_dict(r) for r in rows]

    def get_stats(self) -> dict[str, Any]:
        total = self._db.execute(
            "SELECT COUNT(*) as cnt FROM contracts"
        ).fetchone()["cnt"]

        by_type = {}
        rows = self._db.execute(
            "SELECT contract_type, COUNT(*) as cnt FROM contracts GROUP BY contract_type"
        ).fetchall()
        for r in rows:
            by_type[r["contract_type"]] = r["cnt"]

        by_status = {}
        rows = self._db.execute(
            "SELECT status, COUNT(*) as cnt FROM contracts GROUP BY status"
        ).fetchall()
        for r in rows:
            by_status[r["status"]] = r["cnt"]

        tags = self._db.execute(
            "SELECT tag, COUNT(*) as cnt FROM contract_tags GROUP BY tag ORDER BY cnt DESC LIMIT 20"
        ).fetchall()
        top_tags = [{"tag": r["tag"], "count": r["cnt"]} for r in tags]

        return {
            "total": total,
            "by_type": by_type,
            "by_status": by_status,
            "top_tags": top_tags,
        }

    def _row_to_dict(self, row) -> dict[str, Any]:
        result = {
            "contract_id": row["contract_id"],
            "contract_type": row["contract_type"],
            "content": json.loads(row["content_json"]) if row["content_json"] else {},
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version": row["version"],
            "status": row["status"],
            "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None,
        }

        tags = self._db.execute(
            "SELECT tag FROM contract_tags WHERE contract_id=?",
            (row["contract_id"],),
        ).fetchall()
        result["tags"] = [t["tag"] for t in tags]

        deps = self._db.execute(
            "SELECT depends_on_contract_id FROM contract_dependencies WHERE contract_id=?",
            (row["contract_id"],),
        ).fetchall()
        result["dependencies"] = [d["depends_on_contract_id"] for d in deps]

        return result

    def _bump_version(self, version: str) -> str:
        parts = version.split(".")
        try:
            patch = int(parts[-1]) + 1
            return ".".join(parts[:-1] + [str(patch)])
        except (ValueError, IndexError):
            return "1.0.1"
